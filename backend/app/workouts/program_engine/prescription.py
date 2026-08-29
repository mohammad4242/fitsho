import math
from collections import Counter
from dataclasses import dataclass

from app.exercises.enums import ExerciseType, PrescriptionMode
from app.workouts.program_engine.duration_policy import (
    calculate_total_session_minutes_from_exercises,
    is_main_training_exercise,
)
from app.workouts.program_engine.enums import Goal, TrainingStatus
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    NormalizedProgramRequest,
    ProgrammedExercise,
    SessionDraft,
    WeeklyVolumePlan,
    WorkoutDay,
)
from app.workouts.program_engine.session_targets import english_session_title
from app.workouts.program_engine.strength_programming import (
    STRENGTH_PRIMARY_LIFT_SET_CAP_AUTHORIZED,
    StrengthExerciseRole,
    classify_strength_role,
    is_strength_set_cap_authorized,
)
from app.workouts.program_engine.supplemental_policy import (
    contextual_minimum_working_sets,
    is_core_or_supplemental_exercise,
)


@dataclass(frozen=True)
class ExercisePrescription:
    mode: PrescriptionMode
    rep_min: int | None
    rep_max: int | None
    duration_min_seconds: int | None
    duration_max_seconds: int | None
    target_rir: int | None
    rest_seconds: int
    minimum_rest_seconds: int
    maximum_rest_seconds: int


def prescribe_sessions(
    request: NormalizedProgramRequest,
    drafts: tuple[SessionDraft, ...],
    volume: WeeklyVolumePlan,
    ruleset: ProgramRuleset,
) -> tuple[WorkoutDay, ...]:
    appearances = Counter(
        item.primary_muscle
        for draft in drafts
        for item in draft.exercises
        if item.primary_muscle is not None
    )
    exposure_counts = Counter(
        muscle
        for draft in drafts
        for muscle in {item.primary_muscle for item in draft.exercises}
        if muscle is not None
    )
    allocation_minimums: dict[object, int] = {}
    for draft in drafts:
        for item in draft.exercises:
            if item.primary_muscle is None:
                continue
            contextual_minimum = contextual_minimum_working_sets(
                item,
                ruleset.minimum_working_sets,
            )
            allocation_minimums[item.primary_muscle] = min(
                allocation_minimums.get(item.primary_muscle, ruleset.minimum_working_sets),
                contextual_minimum,
            )
    targets = {target.muscle: target for target in volume.targets}
    allocations = {
        muscle: iter(
            allocate_direct_sets(
                volume.direct_sets_for(muscle),
                count,
                allocation_minimums.get(muscle, ruleset.minimum_working_sets),
            )
        )
        for muscle, count in appearances.items()
        if volume.direct_sets_for(muscle) > 0
    }
    days: list[WorkoutDay] = []
    for _day_index, draft in enumerate(drafts):
        main_exercise_count = max(
            1,
            sum(is_main_training_exercise(exercise) for exercise in draft.exercises),
        )
        # available = full resistance budget; cardio is scheduled outside/after.
        available = max(
            ruleset.minimum_session_work_minutes,
            request.source.session_duration_minutes,
        )
        per_exercise_budget = max(
            ruleset.minimum_exercise_budget_minutes,
            available // main_exercise_count,
        )
        programmed: list[ProgrammedExercise] = []
        direct_session_sets: Counter[object] = Counter()
        ordered_exercises = (
            sorted(
                draft.exercises,
                key=lambda exercise: ruleset.strength_role_order[
                    classify_strength_role(exercise, request, ruleset).role.value
                ],
            )
            if request.primary_goal is Goal.STRENGTH
            else draft.exercises
        )
        for exercise in ordered_exercises:
            strength_role = (
                classify_strength_role(exercise, request, ruleset)
                if request.primary_goal is Goal.STRENGTH
                else None
            )
            is_primary_strength = (
                strength_role is not None
                and strength_role.role is StrengthExerciseRole.PRIMARY_STRENGTH
            )
            strength_set_cap_authorized = is_strength_set_cap_authorized(
                goal=request.primary_goal,
                exercise_type=exercise.exercise_type,
                exercise_slug=exercise.slug,
                is_primary_strength=is_primary_strength,
            )
            primary_muscle = exercise.primary_muscle
            core_or_supplemental = is_core_or_supplemental_exercise(exercise)
            minimum_working_sets = contextual_minimum_working_sets(
                exercise,
                ruleset.minimum_working_sets,
            )
            session_size_accessory = False
            if primary_muscle is not None:
                from app.workouts.program_engine.volume_policy import session_hard_volume_cap

                sess_max = session_hard_volume_cap(request.source.training_age_months)
            else:
                sess_max = ruleset.max_sets_per_muscle_per_session

            if primary_muscle in allocations:
                allocated_sets = next(allocations[primary_muscle])
                sets = max(minimum_working_sets, allocated_sets)
                session_size_accessory = allocated_sets < minimum_working_sets
            else:
                sets = (
                    minimum_working_sets
                    if core_or_supplemental
                    else min(sess_max, ruleset.default_untracked_muscle_sets)
                )
            if primary_muscle is not None:
                remaining_direct_sets = sess_max - direct_session_sets[primary_muscle]
                if remaining_direct_sets >= minimum_working_sets:
                    sets = min(sets, remaining_direct_sets)
                direct_session_sets[primary_muscle] += sets
            cap = ruleset.max_working_sets_for_exercise(
                training_status=request.training_status,
                goal=request.primary_goal,
                exercise_type=exercise.exercise_type,
                is_priority=(
                    targets[primary_muscle].direct_minimum_required
                    if primary_muscle is not None and primary_muscle in targets
                    else primary_muscle in request.source.priority_muscles
                ),
                weekly_exposure_count=(
                    exposure_counts[primary_muscle] if primary_muscle is not None else 0
                ),
                is_primary_strength=is_primary_strength,
                is_approved_primary_strength_lift=strength_set_cap_authorized,
            )
            cap_applied = sets > cap
            sets = min(sets, cap)
            prescription = prescription_for(
                request.primary_goal,
                exercise.exercise_type,
                request.training_status,
                ruleset,
                prescription_mode=exercise.prescription_mode,
                duration_min_seconds=exercise.duration_min_seconds,
                duration_max_seconds=exercise.duration_max_seconds,
                strength_role=strength_role.role if strength_role is not None else None,
                fatigue_cost=exercise.fatigue_cost,
            )
            rest = prescription.rest_seconds
            warmup_sets = 0
            if (
                not any(item.exercise_type is ExerciseType.COMPOUND for item in programmed)
                and exercise.exercise_type is ExerciseType.COMPOUND
            ):
                warmup_sets = (
                    ruleset.strength_compound_warmup_sets
                    if request.primary_goal is Goal.STRENGTH
                    else ruleset.first_compound_warmup_sets
                )
            while (
                is_main_training_exercise(exercise)
                and sets > ruleset.minimum_working_sets
                and estimate_exercise_minutes(sets, rest, warmup_sets, ruleset)
                > per_exercise_budget
            ):
                sets -= 1
            programmed.append(
                ProgrammedExercise(
                    exercise_id=exercise.id,
                    exercise_name=exercise.name,
                    order=len(programmed) + 1,
                    sets=sets,
                    rep_min=prescription.rep_min,
                    rep_max=prescription.rep_max,
                    duration_min_seconds=prescription.duration_min_seconds,
                    duration_max_seconds=prescription.duration_max_seconds,
                    prescription_mode=prescription.mode,
                    target_rir=prescription.target_rir,
                    rest_seconds=rest,
                    estimated_minutes=estimate_exercise_minutes(sets, rest, warmup_sets, ruleset),
                    reason_codes=tuple(
                        dict.fromkeys(
                            draft.selection_reasons[exercise.id]
                            + (strength_role.reason_codes if strength_role is not None else ())
                            + (
                                (STRENGTH_PRIMARY_LIFT_SET_CAP_AUTHORIZED,)
                                if strength_set_cap_authorized
                                else ()
                            )
                            + (("VOLUME_SET_CAP_APPLIED",) if cap_applied else ())
                            + (("SESSION_SIZE_ACCESSORY",) if session_size_accessory else ())
                        )
                    ),
                    substitution_exercise_ids=draft.substitutions[exercise.id],
                    warmup_sets=warmup_sets,
                    counts_toward_volume=True,
                    movement_pattern=exercise.movement_pattern,
                    primary_muscle=exercise.primary_muscle,
                    secondary_muscles=exercise.secondary_muscles,
                    equipment=exercise.equipment,
                    caution_tags=exercise.caution_tags,
                    range_of_motion_profile=exercise.range_of_motion_profile,
                    impact_level=exercise.impact_level,
                    axial_loading_level=exercise.axial_loading_level,
                    stability_demand=exercise.stability_demand,
                    muscle_focus=exercise.muscle_focus,
                    body_position=exercise.body_position,
                    laterality=exercise.laterality,
                    substitution_group=exercise.substitution_group,
                    is_active=exercise.is_active,
                    is_programmable=exercise.is_programmable,
                    needs_review=exercise.needs_review,
                    exercise_type=exercise.exercise_type,
                    exercise_slug=exercise.slug,
                )
            )
        estimated = calculate_total_session_minutes_from_exercises(
            programmed,
            ruleset.general_warmup_minutes,
        )
        days.append(
            WorkoutDay(
                day_index=draft.day_index,
                weekday=draft.weekday,
                title=english_session_title(draft.day_index, programmed),
                focus=draft.focus,
                estimated_duration_minutes=estimated,
                exercises=tuple(programmed),
                template_target_muscles=draft.template_target_muscles,
                template_structure_focus=draft.template_structure_focus,
            )
        )
    return tuple(days)


def allocate_direct_sets(
    target_sets: int,
    appearance_count: int,
    minimum_working_sets: int,
) -> tuple[int, ...]:
    """Allocate a weekly direct-set target exactly without forced round-up."""
    if target_sets < 0 or appearance_count < 0 or minimum_working_sets < 1:
        raise ValueError("invalid direct-set allocation inputs")
    if appearance_count == 0:
        return ()
    active_appearances = min(appearance_count, target_sets // minimum_working_sets)
    if active_appearances == 0:
        return (0,) * appearance_count
    base, remainder = divmod(target_sets, active_appearances)
    return tuple(
        base + (1 if index < remainder else 0) if index < active_appearances else 0
        for index in range(appearance_count)
    )


def prescription_for(
    goal: Goal,
    exercise_type: ExerciseType,
    status: TrainingStatus,
    ruleset: ProgramRuleset,
    prescription_mode: PrescriptionMode = PrescriptionMode.REPS,
    duration_min_seconds: int | None = None,
    duration_max_seconds: int | None = None,
    strength_role: StrengthExerciseRole | None = None,
    fatigue_cost: int = 2,
) -> ExercisePrescription:
    role: StrengthExerciseRole | None = None
    if exercise_type is ExerciseType.CORE:
        key = "core"
    elif goal is Goal.STRENGTH:
        if exercise_type is ExerciseType.ISOLATION:
            key = "strength_isolation"
            role = StrengthExerciseRole.ACCESSORY
        else:
            role = strength_role or StrengthExerciseRole.SECONDARY_COMPOUND
            key = {
                StrengthExerciseRole.PRIMARY_STRENGTH: "strength_compound",
                StrengthExerciseRole.SECONDARY_COMPOUND: "strength_secondary_compound",
                StrengthExerciseRole.ACCESSORY: "strength_accessory",
            }[role]
    elif goal in {Goal.HYPERTROPHY, Goal.MUSCLE_GAIN}:
        key = (
            "hypertrophy_isolation"
            if exercise_type is ExerciseType.ISOLATION
            else "hypertrophy_compound"
        )
    elif goal is Goal.MUSCULAR_ENDURANCE:
        key = "muscular_endurance"
    elif goal in {Goal.FAT_LOSS, Goal.BODY_RECOMPOSITION}:
        key = (
            "fat_loss_isolation" if exercise_type is ExerciseType.ISOLATION else "fat_loss_compound"
        )
    else:
        key = (
            "general_fitness_isolation"
            if exercise_type is ExerciseType.ISOLATION
            else "general_fitness_compound"
        )
    rule = ruleset.prescription_rules[key]
    rir = ruleset.target_rir_rules[key][status]
    rep_min = rule.rep_min
    rep_max = rule.rep_max
    rest_seconds = rule.rest_seconds
    if goal is Goal.STRENGTH and role is not None:
        if (
            role is not StrengthExerciseRole.PRIMARY_STRENGTH
            and fatigue_cost >= ruleset.strength_high_fatigue_cost
        ):
            rest_seconds = min(
                rule.maximum_rest_seconds,
                rest_seconds + ruleset.strength_high_fatigue_rest_bonus_seconds,
            )
    if prescription_mode is PrescriptionMode.REPS:
        return ExercisePrescription(
            mode=PrescriptionMode.REPS,
            rep_min=rep_min,
            rep_max=rep_max,
            duration_min_seconds=None,
            duration_max_seconds=None,
            target_rir=rir,
            rest_seconds=rest_seconds,
            minimum_rest_seconds=rule.minimum_rest_seconds,
            maximum_rest_seconds=rule.maximum_rest_seconds,
        )
    if prescription_mode is PrescriptionMode.DURATION:
        if (
            duration_min_seconds is None
            or duration_max_seconds is None
            or not 1 <= duration_min_seconds <= duration_max_seconds <= 3600
        ):
            raise ValueError("duration prescriptions require valid exercise metadata")
        return ExercisePrescription(
            mode=PrescriptionMode.DURATION,
            rep_min=None,
            rep_max=None,
            duration_min_seconds=duration_min_seconds,
            duration_max_seconds=duration_max_seconds,
            target_rir=None,
            rest_seconds=rest_seconds,
            minimum_rest_seconds=rule.minimum_rest_seconds,
            maximum_rest_seconds=rule.maximum_rest_seconds,
        )
    raise ValueError(f"unsupported prescription mode: {prescription_mode}")


def estimate_exercise_minutes(
    sets: int,
    rest_seconds: int,
    warmup_sets: int,
    ruleset: ProgramRuleset,
) -> int:
    work = sets * ruleset.set_execution_minutes
    rest = max(0, sets - 1) * rest_seconds / 60
    ramp_up = warmup_sets * ruleset.warmup_set_minutes
    return max(
        ruleset.minimum_exercise_estimate_minutes,
        math.ceil(ruleset.exercise_transition_minutes + work + rest + ramp_up),
    )
