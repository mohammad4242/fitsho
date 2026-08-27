import math
from collections import Counter
from dataclasses import replace

from app.exercises.enums import MovementPattern, MuscleGroup
from app.workouts.program_engine.duration_policy import get_session_duration_policy
from app.workouts.program_engine.effective_volume import calculate_effective_volume
from app.workouts.program_engine.enums import Goal
from app.workouts.program_engine.exercise_ranker import rank_exercises
from app.workouts.program_engine.exercise_semantics import has_near_equivalent
from app.workouts.program_engine.prescription import (
    estimate_exercise_minutes,
    prescription_for,
)
from app.workouts.program_engine.priority_allocation import PriorityAllocationPolicy
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    ProgrammedExercise,
    VolumeTarget,
    WeeklyVolumePlan,
    WorkoutDay,
)
from app.workouts.program_engine.session_builder import exercise_fits_focus
from app.workouts.program_engine.session_targets import english_session_title
from app.workouts.program_engine.strength_programming import classify_strength_role
from app.workouts.program_engine.substitution_engine import (
    SubstitutionContext,
    SubstitutionDecision,
    rank_substitutions,
)
from app.workouts.program_engine.substitution_policy import SubstitutionCause
from app.workouts.program_engine.supplemental_policy import main_exercise_count
from app.workouts.program_engine.template_sessions import adaptation_preservation_rank

_HARD_MOVEMENT_PATTERN_GROUPS = (
    frozenset({MovementPattern.HORIZONTAL_PUSH, MovementPattern.VERTICAL_PUSH}),
    frozenset({MovementPattern.HORIZONTAL_PULL, MovementPattern.VERTICAL_PULL}),
    frozenset({MovementPattern.SQUAT, MovementPattern.LUNGE, MovementPattern.KNEE_EXTENSION}),
    frozenset({MovementPattern.HIP_HINGE, MovementPattern.HIP_EXTENSION}),
    frozenset(
        {
            MovementPattern.CORE_ANTI_EXTENSION,
            MovementPattern.CORE_ANTI_ROTATION,
            MovementPattern.CORE_ANTI_LATERAL_FLEXION,
        }
    ),
)


def repair_weekly_volume(
    days: tuple[WorkoutDay, ...],
    request: NormalizedProgramRequest,
    volume: WeeklyVolumePlan,
    ruleset: ProgramRuleset,
    *,
    candidates: tuple[ExerciseCandidate, ...] = (),
    allow_soft_exercise_additions: bool = True,
    preserve_template_core_structure: bool = False,
    substitution_decisions: list[SubstitutionDecision] | None = None,
) -> tuple[tuple[WorkoutDay, ...], tuple[str, ...]]:
    """Keep effective volume inside targets and hard caps before validation.

    The deterministic repair first removes excess volume, then adds sets only
    when effective or required direct volume is still below its target.
    """
    repaired = [list(day.exercises) for day in days]
    targets = {target.muscle: target for target in volume.targets}
    priority_policy = PriorityAllocationPolicy.for_request(request, ruleset)
    reasons: list[str] = []
    total_sets = sum(item.sets for day in days for item in day.exercises)
    max_iterations = max(total_sets * 2, 1)
    iteration = 0
    while True:
        if iteration >= max_iterations:
            reasons.append("VOLUME_REPAIR_ITERATION_LIMIT_REACHED")
            break
        iteration += 1
        effective_volume = calculate_effective_volume(
            (item for exercises in repaired for item in exercises),
            ruleset,
        )
        direct = Counter(effective_volume.direct_sets_by_muscle)
        effective = effective_volume.effective_sets_by_muscle
        weekly_excessive = {
            muscle
            for muscle, sets in effective.items()
            if sets > _maximum_for(muscle, targets, ruleset, request)
        }
        hard_weekly_excessive = {
            muscle
            for muscle, sets in effective.items()
            if sets > _hard_maximum_for(muscle, targets, ruleset, request)
        }
        per_session_excessive = _per_session_excessive(repaired, ruleset)
        per_exercise_excessive = _per_exercise_excessive(repaired, request, targets, ruleset)
        reduction = _select_reduction_candidate(
            repaired,
            weekly_excessive,
            per_session_excessive,
            direct,
            targets,
            request,
            ruleset,
            per_exercise_excessive,
            hard_weekly_excessive,
            preserve_template_core_structure,
        )
        if reduction is not None:
            day_index, exercise_index, exercise = reduction
            if exercise.sets > ruleset.minimum_working_sets:
                priority_over_target = (
                    exercise.primary_muscle in priority_policy.priorities
                    and exercise.primary_muscle in targets
                    and direct.get(exercise.primary_muscle.value, 0)
                    > targets[exercise.primary_muscle].target_sets
                )
                reduction_reason = (
                    "VOLUME_REPAIR_REDUCED_SET_FOR_EXERCISE_CAP"
                    if (day_index, exercise_index) in per_exercise_excessive
                    else "VOLUME_REPAIR_REDUCED_SET"
                )
                repaired[day_index][exercise_index] = replace(
                    exercise,
                    sets=exercise.sets - 1,
                    estimated_minutes=estimate_exercise_minutes(
                        exercise.sets - 1,
                        exercise.rest_seconds,
                        exercise.warmup_sets,
                        ruleset,
                    ),
                    reason_codes=exercise.reason_codes
                    + (reduction_reason,)
                    + (
                        ("VOLUME_REPAIR_RELAXED_DIRECT_MINIMUM_FOR_HARD_CAP",)
                        if _direct_minimum_relaxed_for_hard_cap(
                            exercise,
                            direct,
                            targets,
                            hard_weekly_excessive,
                        )
                        else ()
                    ),
                )
                reasons.append(reduction_reason)
                if priority_over_target:
                    reasons.append("PRIORITY_VOLUME_REDISTRIBUTED")
                continue
            same_muscle_exposures = sum(
                1
                for exercises in repaired
                for item in exercises
                if item.primary_muscle is exercise.primary_muscle
            )
            if exercise.primary_muscle is None:
                continue
            affected_muscles = {exercise.primary_muscle.value} | {
                muscle.value for muscle in exercise.secondary_muscles
            }
            hard_removal_required = bool(
                affected_muscles.intersection(hard_weekly_excessive)
                or (day_index, exercise.primary_muscle) in per_session_excessive
                or (day_index, exercise_index) in per_exercise_excessive
            )
            if (same_muscle_exposures > 1 or hard_removal_required) and (
                len(repaired[day_index]) > ruleset.minimum_exercises_per_session
                or preserve_template_core_structure
                or hard_removal_required
            ):
                repaired[day_index].pop(exercise_index)
                reasons.append("VOLUME_REPAIR_REMOVED_REDUNDANT_EXERCISE")
                if _direct_minimum_relaxed_for_hard_cap(
                    exercise,
                    direct,
                    targets,
                    hard_weekly_excessive,
                ):
                    reasons.append("VOLUME_REPAIR_RELAXED_DIRECT_MINIMUM_FOR_HARD_CAP")
                continue

        direct_under = {
            muscle
            for muscle, target in targets.items()
            if direct.get(muscle.value, 0) < target.minimum_direct_sets
        }
        effective_under = {
            muscle
            for muscle, target in targets.items()
            if effective.get(muscle.value, 0) < target.effective_target_sets
        }
        hard_direct_under = {
            muscle for muscle in direct_under if targets[muscle].direct_minimum_required
        }
        hard_effective_under = {
            muscle
            for muscle, target in targets.items()
            if target.minimum_coverage_required
            and effective.get(muscle.value, 0) < target.minimum_effective_sets
        }
        repairing_hard_minimum = bool(hard_direct_under or hard_effective_under)
        if repairing_hard_minimum and hard_direct_under:
            redistribution = _select_set_redistribution(
                repaired,
                hard_direct_under,
                targets,
                request,
                ruleset,
            )
            if redistribution is not None:
                day_index, recipient_index, donor_index = redistribution
                recipient = repaired[day_index][recipient_index]
                donor = repaired[day_index][donor_index]
                repaired[day_index][recipient_index] = replace(
                    recipient,
                    sets=recipient.sets + 1,
                    estimated_minutes=estimate_exercise_minutes(
                        recipient.sets + 1,
                        recipient.rest_seconds,
                        recipient.warmup_sets,
                        ruleset,
                    ),
                    reason_codes=recipient.reason_codes
                    + ("VOLUME_REPAIR_REDISTRIBUTED_SET_TO_DIRECT_MINIMUM",),
                )
                repaired[day_index][donor_index] = replace(
                    donor,
                    sets=donor.sets - 1,
                    estimated_minutes=estimate_exercise_minutes(
                        donor.sets - 1,
                        donor.rest_seconds,
                        donor.warmup_sets,
                        ruleset,
                    ),
                    reason_codes=donor.reason_codes
                    + ("VOLUME_REPAIR_REDISTRIBUTED_SET_FROM_SURPLUS",),
                )
                reasons.append("VOLUME_REPAIR_REDISTRIBUTED_SET_FOR_MINIMUM_COVERAGE")
                continue
        exercise_addition = _select_exercise_addition(
            repaired,
            days,
            hard_direct_under,
            hard_effective_under,
            candidates,
            request,
            targets,
            ruleset,
            use_hard_maximums=repairing_hard_minimum,
        )
        if (
            exercise_addition is None
            and not repairing_hard_minimum
            and allow_soft_exercise_additions
        ):
            exercise_addition = _select_exercise_addition(
                repaired,
                days,
                direct_under,
                effective_under,
                candidates,
                request,
                targets,
                ruleset,
                use_hard_maximums=False,
            )
        if exercise_addition is not None:
            day_index, programmed, substitution_decision = exercise_addition
            if substitution_decisions is not None:
                substitution_decisions.append(substitution_decision)
            if (
                programmed.primary_muscle in priority_policy.priorities
                and request.primary_goal is not Goal.STRENGTH
            ):
                repaired[day_index].insert(0, programmed)
            else:
                repaired[day_index].append(programmed)
            reasons.append("VOLUME_REPAIR_ADDED_EXERCISE_FOR_MINIMUM_COVERAGE")
            if programmed.primary_muscle in priority_policy.priorities:
                reasons.append("PRIORITY_VOLUME_REDISTRIBUTED")
            continue
        addition = _select_addition_candidate(
            repaired,
            hard_direct_under if repairing_hard_minimum else direct_under,
            hard_effective_under if repairing_hard_minimum else effective_under,
            direct,
            targets,
            request,
            ruleset,
            use_hard_maximums=repairing_hard_minimum,
        )
        if addition is None:
            if repairing_hard_minimum:
                soft_addition = _select_addition_candidate(
                    repaired,
                    direct_under,
                    effective_under,
                    direct,
                    targets,
                    request,
                    ruleset,
                    use_hard_maximums=False,
                )
                if soft_addition is not None:
                    day_index, exercise_index, exercise, reason = soft_addition
                    repaired[day_index][exercise_index] = replace(
                        exercise,
                        sets=exercise.sets + 1,
                        estimated_minutes=estimate_exercise_minutes(
                            exercise.sets + 1,
                            exercise.rest_seconds,
                            exercise.warmup_sets,
                            ruleset,
                        ),
                        reason_codes=exercise.reason_codes + (reason,),
                    )
                    reasons.append(reason)
                    continue
            reasons.append(
                "VOLUME_REPAIR_HARD_MINIMUM_UNSATISFIED"
                if repairing_hard_minimum
                else "VOLUME_REPAIR_SOFT_TARGET_REDUCED"
            )
            break
        day_index, exercise_index, exercise, reason = addition
        repaired[day_index][exercise_index] = replace(
            exercise,
            sets=exercise.sets + 1,
            estimated_minutes=estimate_exercise_minutes(
                exercise.sets + 1,
                exercise.rest_seconds,
                exercise.warmup_sets,
                ruleset,
            ),
            reason_codes=exercise.reason_codes + (reason,),
        )
        reasons.append(reason)
        if exercise.primary_muscle in priority_policy.priorities:
            reasons.append("PRIORITY_VOLUME_REDISTRIBUTED")

    return _rebuild_days(days, repaired, ruleset), tuple(dict.fromkeys(reasons))


def _select_set_redistribution(
    days: list[list[ProgrammedExercise]],
    hard_direct_under: set[MuscleGroup],
    targets: dict[MuscleGroup, VolumeTarget],
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
) -> tuple[int, int, int] | None:
    duration_policy = get_session_duration_policy(
        request.source.session_duration_minutes,
    )
    priority_policy = PriorityAllocationPolicy.for_request(request, ruleset)
    direct = _direct_sets(days)
    options: list[tuple[int, int, int, int, str, str]] = []
    for day_index, exercises in enumerate(days):
        direct_by_session = _direct_sets([exercises])
        for recipient_index, recipient in enumerate(exercises):
            recipient_muscle = recipient.primary_muscle
            if (
                recipient_muscle not in hard_direct_under
                or direct_by_session[recipient_muscle] >= ruleset.max_sets_per_muscle_per_session
                or recipient.sets >= _exercise_set_cap(recipient, days, request, targets, ruleset)
            ):
                continue
            for donor_index, donor in enumerate(exercises):
                donor_muscle = donor.primary_muscle
                if (
                    donor_index == recipient_index
                    or donor_muscle is None
                    or donor.sets <= ruleset.minimum_working_sets
                ):
                    continue
                donor_target = targets.get(donor_muscle)
                if priority_policy.preservation_rank(
                    donor_muscle
                ) > priority_policy.preservation_rank(recipient_muscle):
                    continue
                if (
                    donor_target is not None
                    and donor_target.direct_minimum_required
                    and direct[donor_muscle] - 1 < donor_target.minimum_direct_sets
                ):
                    continue
                updated_recipient = replace(
                    recipient,
                    sets=recipient.sets + 1,
                    estimated_minutes=estimate_exercise_minutes(
                        recipient.sets + 1,
                        recipient.rest_seconds,
                        recipient.warmup_sets,
                        ruleset,
                    ),
                )
                updated_donor = replace(
                    donor,
                    sets=donor.sets - 1,
                    estimated_minutes=estimate_exercise_minutes(
                        donor.sets - 1,
                        donor.rest_seconds,
                        donor.warmup_sets,
                        ruleset,
                    ),
                )
                simulated = [list(items) for items in days]
                simulated[day_index][recipient_index] = updated_recipient
                simulated[day_index][donor_index] = updated_donor
                simulated_volume = calculate_effective_volume(
                    (item for items in simulated for item in items),
                    ruleset,
                )
                if any(
                    target.minimum_coverage_required
                    and muscle not in hard_direct_under
                    and simulated_volume.effective_sets_by_muscle.get(muscle.value, 0)
                    < target.minimum_effective_sets
                    for muscle, target in targets.items()
                ):
                    continue
                duration = ruleset.general_warmup_minutes + sum(
                    item.estimated_minutes for item in simulated[day_index]
                )
                if duration > duration_policy.maximum_total_minutes(ruleset.general_warmup_minutes):
                    continue
                options.append(
                    (
                        priority_policy.preservation_rank(donor_muscle),
                        day_index,
                        recipient_index,
                        donor_index,
                        str(recipient.exercise_id),
                        str(donor.exercise_id),
                    )
                )
    if not options:
        return None
    selected = min(options)
    return selected[1], selected[2], selected[3]


def _select_exercise_addition(
    days: list[list[ProgrammedExercise]],
    originals: tuple[WorkoutDay, ...],
    direct_under: set[MuscleGroup],
    effective_under: set[MuscleGroup],
    candidates: tuple[ExerciseCandidate, ...],
    request: NormalizedProgramRequest,
    targets: dict[MuscleGroup, VolumeTarget],
    ruleset: ProgramRuleset,
    *,
    use_hard_maximums: bool,
) -> tuple[int, ProgrammedExercise, SubstitutionDecision] | None:
    needed = direct_under | effective_under
    if not needed or not candidates:
        return None
    selected_ids = {item.exercise_id for day in days for item in day}
    priority_policy = PriorityAllocationPolicy.for_request(request, ruleset)
    duration_policy = get_session_duration_policy(
        request.source.session_duration_minutes,
    )
    day_contexts = tuple(
        replace(original, exercises=tuple(exercises))
        for original, exercises in zip(originals, days, strict=True)
    )
    priority_order = {muscle: index for index, muscle in enumerate(priority_policy.priorities)}
    options: list[tuple[tuple[object, ...], int, ProgrammedExercise, SubstitutionDecision]] = []
    current_effective = calculate_effective_volume(
        (item for items in days for item in items), ruleset
    )
    current_effective_sets = current_effective.effective_sets_by_muscle
    current_direct_sets = current_effective.direct_sets_by_muscle
    for muscle in sorted(
        needed,
        key=lambda item: (priority_order.get(item, len(priority_order)), item.value),
    ):
        muscle_candidates = tuple(
            candidate
            for candidate in candidates
            if candidate.primary_muscle is muscle and candidate.id not in selected_ids
        )
        if (
            not muscle_candidates
            and use_hard_maximums
            and muscle in direct_under
            and muscle in priority_policy.explicit_priorities
        ):
            muscle_candidates = tuple(
                candidate for candidate in candidates if candidate.primary_muscle is muscle
            )
        for ranked in rank_exercises(request, muscle_candidates, ruleset, needed_muscle=muscle):
            candidate = ranked.exercise
            template_has_target_day = any(
                candidate.primary_muscle in original.template_target_muscles
                for original in originals
                if original.focus.startswith("template_reference")
            )
            repeated_exercise = candidate.id in selected_ids
            required_sets = (
                targets[muscle].minimum_direct_sets - current_direct_sets.get(muscle.value, 0)
                if muscle in direct_under
                else targets[muscle].minimum_effective_sets
                - current_effective_sets.get(muscle.value, 0)
            )
            sets = max(ruleset.minimum_working_sets, math.ceil(required_sets))
            sets = min(sets, ruleset.max_sets_per_muscle_per_session)
            sets = min(sets, _candidate_set_cap(candidate, days, request, targets, ruleset))
            prescription = prescription_for(
                request.primary_goal,
                candidate.exercise_type,
                request.training_status,
                ruleset,
                prescription_mode=candidate.prescription_mode,
                duration_min_seconds=candidate.duration_min_seconds,
                duration_max_seconds=candidate.duration_max_seconds,
                strength_role=(
                    classify_strength_role(candidate, request, ruleset).role
                    if request.primary_goal is Goal.STRENGTH
                    else None
                ),
                fatigue_cost=candidate.fatigue_cost,
            )
            estimated = estimate_exercise_minutes(sets, prescription.rest_seconds, 0, ruleset)
            for day_index, (day, original) in enumerate(zip(days, originals, strict=True)):
                if main_exercise_count(day) >= ruleset.max_exercises_per_session:
                    continue
                if any(item.exercise_id == candidate.id for item in day):
                    continue
                if has_near_equivalent(candidate, day):
                    continue
                if original.focus.startswith("template_reference"):
                    if (
                        template_has_target_day
                        and candidate.primary_muscle not in original.template_target_muscles
                        and not (
                            use_hard_maximums
                            and candidate.primary_muscle in priority_policy.explicit_priorities
                        )
                    ):
                        continue
                elif not exercise_fits_focus(candidate, original.focus):
                    continue
                direct_by_session = _direct_sets([day])
                session_overage = (
                    direct_by_session[muscle] + sets - ruleset.max_sets_per_muscle_per_session
                )
                if session_overage > 0:
                    reducible_same_muscle = sum(
                        max(0, item.sets - ruleset.minimum_working_sets)
                        for item in day
                        if item.primary_muscle is muscle
                    )
                    if (
                        not use_hard_maximums
                        or session_overage > reducible_same_muscle
                        or direct_by_session[muscle] + sets - session_overage
                        < targets[muscle].minimum_direct_sets
                    ):
                        continue
                current_frequency = _weekly_exposure_count(days, muscle)
                adds_exposure = not any(item.primary_muscle is muscle for item in day)
                frequency_cap = _direct_frequency_cap(len(days), ruleset)
                if current_frequency + int(adds_exposure) > frequency_cap:
                    continue
                duration = (
                    ruleset.general_warmup_minutes
                    + sum(item.estimated_minutes for item in day)
                    + estimated
                )
                if duration > duration_policy.maximum_total_minutes(ruleset.general_warmup_minutes):
                    continue
                role_repeated = any(
                    item.primary_muscle is muscle
                    and item.movement_pattern is candidate.movement_pattern
                    for item in day
                )
                reasons = [
                    *ranked.reason_codes,
                    "VOLUME_REPAIR_ADDED_EXERCISE_FOR_MINIMUM_COVERAGE",
                ]
                if role_repeated:
                    reasons.append("DELIBERATE_REDUNDANCY_FOR_MINIMUM_COVERAGE")
                if repeated_exercise:
                    reasons.append("PRIORITY_EXERCISE_REPEATED_FOR_HARD_MINIMUM")
                substitution_decision = rank_substitutions(
                    request,
                    candidate,
                    list(candidates),
                    SubstitutionContext(cause=SubstitutionCause.VOLUME_REPAIR),
                    ruleset=ruleset,
                    limit=ruleset.substitution_limit,
                )
                substitutions = substitution_decision.exercise_ids
                programmed = ProgrammedExercise(
                    exercise_id=candidate.id,
                    exercise_name=candidate.name,
                    order=len(day) + 1,
                    sets=sets,
                    rep_min=prescription.rep_min,
                    rep_max=prescription.rep_max,
                    duration_min_seconds=prescription.duration_min_seconds,
                    duration_max_seconds=prescription.duration_max_seconds,
                    prescription_mode=prescription.mode,
                    target_rir=prescription.target_rir,
                    rest_seconds=prescription.rest_seconds,
                    estimated_minutes=estimated,
                    reason_codes=tuple(dict.fromkeys(reasons)),
                    substitution_exercise_ids=substitutions,
                    movement_pattern=candidate.movement_pattern,
                    primary_muscle=candidate.primary_muscle,
                    secondary_muscles=candidate.secondary_muscles,
                    equipment=candidate.equipment,
                    caution_tags=candidate.caution_tags,
                    range_of_motion_profile=candidate.range_of_motion_profile,
                    impact_level=candidate.impact_level,
                    axial_loading_level=candidate.axial_loading_level,
                    stability_demand=candidate.stability_demand,
                    muscle_focus=candidate.muscle_focus,
                    body_position=candidate.body_position,
                    laterality=candidate.laterality,
                    substitution_group=candidate.substitution_group,
                    is_active=candidate.is_active,
                    is_programmable=candidate.is_programmable,
                    needs_review=candidate.needs_review,
                    exercise_type=candidate.exercise_type,
                )
                simulated = [list(items) for items in days]
                simulated[day_index].append(programmed)
                simulated_volume = calculate_effective_volume(
                    (item for items in simulated for item in items),
                    ruleset,
                )
                violations = tuple(
                    (target_muscle, target, simulated_sets)
                    for target_muscle, target in targets.items()
                    if (
                        simulated_sets := simulated_volume.effective_sets_by_muscle.get(
                            target_muscle.value, 0
                        )
                    )
                    > (target.maximum_hard if use_hard_maximums else target.acceptable_maximum)
                    and simulated_sets > current_effective_sets.get(target_muscle.value, 0)
                )
                if violations and not _repairable_direct_priority_overage(
                    violations,
                    candidate,
                    day,
                    simulated_volume.direct_sets_by_muscle,
                    direct_under,
                    ruleset,
                ):
                    continue
                options.append(
                    (
                        (
                            0 if muscle in direct_under else 1,
                            0 if muscle in priority_policy.priorities else 1,
                            *priority_policy.day_priority_key(
                                day_contexts,
                                muscle,
                                day_index,
                                preferred_frequency=priority_policy.useful_frequency(
                                    targets[muscle].target_sets,
                                    ruleset,
                                ),
                            ),
                            direct_by_session[muscle],
                            -ranked.score,
                            1 if role_repeated else 0,
                            str(candidate.id),
                        ),
                        day_index,
                        programmed,
                        substitution_decision,
                    )
                )
    if not options:
        return None
    selected = min(options, key=lambda item: item[0])
    return selected[1], selected[2], selected[3]


def _repairable_direct_priority_overage(
    violations: tuple[tuple[MuscleGroup, VolumeTarget, float], ...],
    candidate: ExerciseCandidate,
    day: list[ProgrammedExercise],
    simulated_direct_sets: dict[str, int],
    direct_under: set[MuscleGroup],
    ruleset: ProgramRuleset,
) -> bool:
    if len(violations) != 1 or candidate.primary_muscle not in direct_under:
        return False
    muscle, target, simulated_effective = violations[0]
    if muscle is not candidate.primary_muscle:
        return False
    direct_overage = simulated_direct_sets.get(muscle.value, 0) - target.minimum_direct_sets
    reducible_existing_sets = sum(
        max(0, item.sets - ruleset.minimum_working_sets)
        for item in day
        if item.primary_muscle is muscle
    )
    return (
        direct_overage > 0
        and direct_overage <= reducible_existing_sets
        and simulated_effective - direct_overage <= target.maximum_hard
    )


def _maximum_for(
    muscle: str,
    targets: dict[MuscleGroup, VolumeTarget],
    ruleset: ProgramRuleset,
    request: NormalizedProgramRequest,
) -> int:
    muscle_enum = next((item for item in MuscleGroup if item.value == muscle), None)
    target = targets.get(muscle_enum) if muscle_enum is not None else None
    return (
        target.acceptable_maximum
        if target is not None
        else ruleset.maximum_sets[request.training_status]
    )


def _hard_maximum_for(
    muscle: str,
    targets: dict[MuscleGroup, VolumeTarget],
    ruleset: ProgramRuleset,
    request: NormalizedProgramRequest,
) -> int:
    muscle_enum = next((item for item in MuscleGroup if item.value == muscle), None)
    target = targets.get(muscle_enum) if muscle_enum is not None else None
    return (
        target.maximum_hard if target is not None else ruleset.maximum_sets[request.training_status]
    )


def _select_reduction_candidate(
    days: list[list[ProgrammedExercise]],
    weekly_excessive: set[str],
    per_session_excessive: set[tuple[int, MuscleGroup]],
    direct: Counter[str],
    targets: dict[MuscleGroup, VolumeTarget],
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
    per_exercise_excessive: set[tuple[int, int]],
    hard_weekly_excessive: set[str],
    preserve_template_core_structure: bool,
) -> tuple[int, int, ProgrammedExercise] | None:
    priority_policy = PriorityAllocationPolicy.for_request(request, ruleset)
    priority_over_target = {
        muscle.value
        for muscle, target in targets.items()
        if target.direct_minimum_required and direct.get(muscle.value, 0) > target.target_sets
    }
    candidates = []
    for day_index, exercises in enumerate(days):
        for exercise_index, exercise in enumerate(exercises):
            if exercise.primary_muscle is None:
                continue
            affected = {exercise.primary_muscle.value} | {
                muscle.value for muscle in exercise.secondary_muscles
            }
            is_template_core = "TEMPLATE_ADAPTATION_PRIORITY:core" in exercise.reason_codes
            is_required_slot = any(code.startswith("REQUIRED_") for code in exercise.reason_codes)
            hard_constraint = bool(
                affected.intersection(hard_weekly_excessive)
                or (day_index, exercise.primary_muscle) in per_session_excessive
                or (day_index, exercise_index) in per_exercise_excessive
            )
            if (
                (is_template_core or is_required_slot)
                and exercise.sets <= ruleset.minimum_working_sets
                and not hard_constraint
            ):
                continue
            if (day_index, exercise_index) not in per_exercise_excessive and (
                not affected.intersection(weekly_excessive)
                and (
                    day_index,
                    exercise.primary_muscle,
                )
                not in per_session_excessive
                and exercise.primary_muscle.value not in priority_over_target
            ):
                continue
            minimum_direct = targets.get(exercise.primary_muscle)
            same_muscle_exposures = sum(
                item.primary_muscle is exercise.primary_muscle for items in days for item in items
            )
            reduction_sets = 1 if exercise.sets > ruleset.minimum_working_sets else exercise.sets
            if (
                minimum_direct is not None
                and minimum_direct.direct_minimum_required
                and (day_index, exercise.primary_muscle) not in per_session_excessive
                and direct[exercise.primary_muscle.value] - reduction_sets
                < minimum_direct.minimum_direct_sets
                and not affected.intersection(hard_weekly_excessive)
            ):
                continue
            if (
                exercise.sets <= ruleset.minimum_working_sets
                and same_muscle_exposures <= 1
                and not affected.intersection(hard_weekly_excessive)
            ):
                continue
            if (
                exercise.sets <= ruleset.minimum_working_sets
                and preserve_template_core_structure
                and _is_last_hard_movement_role(exercise, days)
            ):
                continue
            candidates.append((day_index, exercise_index, exercise))
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda candidate: (
            0 if _affected_muscle_values(candidate[2]).intersection(hard_weekly_excessive) else 1,
            adaptation_preservation_rank(candidate[2], priority_policy),
            any(code.startswith("REQUIRED_") for code in candidate[2].reason_codes),
            priority_policy.preservation_rank(candidate[2].primary_muscle),
            -sum(
                item.sets
                for item in days[candidate[0]]
                if item.primary_muscle is candidate[2].primary_muscle
            ),
            -len(days[candidate[0]]),
            -candidate[2].order,
            -candidate[0],
            str(candidate[2].exercise_id),
        ),
    )


def _affected_muscle_values(exercise: ProgrammedExercise) -> set[str]:
    values = {muscle.value for muscle in exercise.secondary_muscles}
    if exercise.primary_muscle is not None:
        values.add(exercise.primary_muscle.value)
    return values


def _direct_minimum_relaxed_for_hard_cap(
    exercise: ProgrammedExercise,
    direct: Counter[str],
    targets: dict[MuscleGroup, VolumeTarget],
    hard_weekly_excessive: set[str],
) -> bool:
    if exercise.primary_muscle is None or not _affected_muscle_values(exercise).intersection(
        hard_weekly_excessive
    ):
        return False
    target = targets.get(exercise.primary_muscle)
    return bool(
        target is not None
        and target.direct_minimum_required
        and direct[exercise.primary_muscle.value] - exercise.sets < target.minimum_direct_sets
    )


def _is_last_hard_movement_role(
    exercise: ProgrammedExercise,
    days: list[list[ProgrammedExercise]],
) -> bool:
    relevant_groups = tuple(
        group for group in _HARD_MOVEMENT_PATTERN_GROUPS if exercise.movement_pattern in group
    )
    return any(
        sum(item.movement_pattern in group for day in days for item in day) <= 1
        for group in relevant_groups
    )


def _select_addition_candidate(
    days: list[list[ProgrammedExercise]],
    direct_under: set[MuscleGroup],
    effective_under: set[MuscleGroup],
    weekly_direct: Counter[str],
    targets: dict[MuscleGroup, VolumeTarget],
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
    *,
    use_hard_maximums: bool = False,
) -> tuple[int, int, ProgrammedExercise, str] | None:
    priority_policy = PriorityAllocationPolicy.for_request(request, ruleset)
    duration_policy = get_session_duration_policy(
        request.source.session_duration_minutes,
    )
    candidates = []
    maximums = {
        muscle.value: (target.maximum_hard if use_hard_maximums else target.acceptable_maximum)
        for muscle, target in targets.items()
    }
    current_effective = calculate_effective_volume(
        (item for items in days for item in items), ruleset
    ).effective_sets_by_muscle
    for day_index, exercises in enumerate(days):
        direct_by_session = _direct_sets([exercises])
        for exercise_index, exercise in enumerate(exercises):
            if exercise.primary_muscle is None:
                continue
            primary = exercise.primary_muscle
            affected = {primary} | set(exercise.secondary_muscles)
            direct_needs = primary in direct_under
            effective_needs = bool(affected.intersection(effective_under))
            if not direct_needs and not effective_needs:
                continue
            primary_target = targets.get(primary)
            if (
                not direct_needs
                and primary_target is not None
                and weekly_direct[primary.value] >= primary_target.direct_sets
            ):
                continue
            if direct_by_session[primary] >= ruleset.max_sets_per_muscle_per_session:
                continue
            if exercise.sets >= _exercise_set_cap(exercise, days, request, targets, ruleset):
                continue
            frequency_target = primary_target or next(
                (targets[muscle] for muscle in affected if muscle in targets),
                None,
            )
            if frequency_target is None:
                continue
            updated = replace(
                exercise,
                sets=exercise.sets + 1,
                estimated_minutes=estimate_exercise_minutes(
                    exercise.sets + 1,
                    exercise.rest_seconds,
                    exercise.warmup_sets,
                    ruleset,
                ),
            )
            if _day_duration(
                exercises,
                exercise,
                updated,
                ruleset,
            ) > duration_policy.maximum_total_minutes(ruleset.general_warmup_minutes):
                continue
            simulated = [list(day_exercises) for day_exercises in days]
            simulated[day_index][exercise_index] = updated
            simulated_volume = calculate_effective_volume(
                (item for items in simulated for item in items),
                ruleset,
            )
            if any(
                simulated_volume.effective_sets_by_muscle.get(muscle, 0) > maximum
                and simulated_volume.effective_sets_by_muscle.get(muscle, 0)
                > current_effective.get(muscle, 0)
                for muscle, maximum in maximums.items()
            ):
                continue
            reason = (
                "VOLUME_REPAIR_ADDED_SET_FOR_DIRECT_MINIMUM"
                if direct_needs
                else "VOLUME_REPAIR_ADDED_SET_FOR_EFFECTIVE_TARGET"
            )
            candidates.append(
                (
                    (
                        0 if direct_needs else 1,
                        0 if primary in effective_under else 1,
                        0 if primary in priority_policy.priorities else 1,
                        *priority_policy.day_priority_key(
                            days,
                            primary,
                            day_index,
                            preferred_frequency=priority_policy.useful_frequency(
                                frequency_target.target_sets,
                                ruleset,
                            ),
                        ),
                        direct_by_session[primary],
                        day_index,
                        exercise_index,
                        str(exercise.exercise_id),
                    ),
                    day_index,
                    exercise_index,
                    exercise,
                    reason,
                )
            )
    if not candidates:
        return None
    selected = min(candidates, key=lambda candidate: candidate[0])
    return selected[1], selected[2], selected[3], selected[4]


def _direct_sets(days: list[list[ProgrammedExercise]]) -> Counter[MuscleGroup]:
    return Counter(
        item.primary_muscle
        for exercises in days
        for item in exercises
        if item.primary_muscle is not None
        for _ in range(item.sets)
    )


def _per_session_excessive(
    days: list[list[ProgrammedExercise]], ruleset: ProgramRuleset
) -> set[tuple[int, MuscleGroup]]:
    excessive: set[tuple[int, MuscleGroup]] = set()
    for day_index, exercises in enumerate(days):
        direct = _direct_sets([exercises])
        excessive.update(
            (day_index, muscle)
            for muscle, sets in direct.items()
            if sets > ruleset.max_sets_per_muscle_per_session
        )
    return excessive


def _per_exercise_excessive(
    days: list[list[ProgrammedExercise]],
    request: NormalizedProgramRequest,
    targets: dict[MuscleGroup, VolumeTarget],
    ruleset: ProgramRuleset,
) -> set[tuple[int, int]]:
    return {
        (day_index, exercise_index)
        for day_index, exercises in enumerate(days)
        for exercise_index, exercise in enumerate(exercises)
        if exercise.sets > _exercise_set_cap(exercise, days, request, targets, ruleset)
    }


def _exercise_set_cap(
    exercise: ProgrammedExercise,
    days: list[list[ProgrammedExercise]],
    request: NormalizedProgramRequest,
    targets: dict[MuscleGroup, VolumeTarget],
    ruleset: ProgramRuleset,
) -> int:
    return ruleset.max_working_sets_for_exercise(
        training_status=request.training_status,
        goal=request.primary_goal,
        exercise_type=exercise.exercise_type,
        is_priority=(
            targets[exercise.primary_muscle].direct_minimum_required
            if exercise.primary_muscle in targets
            else exercise.primary_muscle in request.source.priority_muscles
        ),
        weekly_exposure_count=_weekly_exposure_count(days, exercise.primary_muscle),
        is_primary_strength="STRENGTH_PRIMARY_COMPOUND" in exercise.reason_codes,
    )


def _candidate_set_cap(
    candidate: ExerciseCandidate,
    days: list[list[ProgrammedExercise]],
    request: NormalizedProgramRequest,
    targets: dict[MuscleGroup, VolumeTarget],
    ruleset: ProgramRuleset,
) -> int:
    return ruleset.max_working_sets_for_exercise(
        training_status=request.training_status,
        goal=request.primary_goal,
        exercise_type=candidate.exercise_type,
        is_priority=(
            targets[candidate.primary_muscle].direct_minimum_required
            if candidate.primary_muscle in targets
            else candidate.primary_muscle in request.source.priority_muscles
        ),
        weekly_exposure_count=_weekly_exposure_count(days, candidate.primary_muscle),
        is_primary_strength=False,
    )


def _weekly_exposure_count(days: list[list[ProgrammedExercise]], muscle: MuscleGroup | None) -> int:
    if muscle is None:
        return 0
    return sum(any(item.primary_muscle is muscle for item in exercises) for exercises in days)


def _direct_frequency_cap(training_days: int, ruleset: ProgramRuleset) -> int:
    if training_days <= 4:
        return ruleset.maximum_direct_sessions_per_muscle_per_week
    if training_days == 5:
        return ruleset.maximum_direct_sessions_per_muscle_per_week + 1
    return ruleset.maximum_direct_sessions_per_muscle_per_week + 2


def _rebuild_days(
    originals: tuple[WorkoutDay, ...],
    exercises_by_day: list[list[ProgrammedExercise]],
    ruleset: ProgramRuleset,
) -> tuple[WorkoutDay, ...]:
    repaired_days: list[WorkoutDay] = []
    for original, exercises in zip(originals, exercises_by_day, strict=True):
        reordered = tuple(replace(item, order=index + 1) for index, item in enumerate(exercises))
        repaired_days.append(
            replace(
                original,
                exercises=reordered,
                title=english_session_title(original.day_index, reordered),
                estimated_duration_minutes=(
                    ruleset.general_warmup_minutes
                    + sum(item.estimated_minutes for item in reordered)
                    + (original.cardio.duration_minutes if original.cardio else 0)
                ),
            )
        )
    return tuple(repaired_days)


def _day_duration(
    original_exercises: list[ProgrammedExercise],
    original: ProgrammedExercise,
    updated: ProgrammedExercise,
    ruleset: ProgramRuleset,
) -> int:
    total = sum(item.estimated_minutes for item in original_exercises)
    total += updated.estimated_minutes - original.estimated_minutes
    return ruleset.general_warmup_minutes + total
