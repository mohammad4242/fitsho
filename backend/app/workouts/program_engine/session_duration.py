from collections import Counter
from dataclasses import replace

from app.exercises.enums import ExerciseLabel, ExerciseType, MuscleGroup
from app.workouts.program_engine.duration_capacity import (
    SessionCapacity,
)
from app.workouts.program_engine.duration_policy import (
    SessionDurationPolicy,
    get_session_duration_policy,
)
from app.workouts.program_engine.effective_volume import calculate_effective_volume
from app.workouts.program_engine.enums import Goal
from app.workouts.program_engine.equipment import effective_required_equipment
from app.workouts.program_engine.exercise_ranker import rank_exercises
from app.workouts.program_engine.prescription import (
    ExercisePrescription,
    estimate_exercise_minutes,
    prescription_for,
)
from app.workouts.program_engine.priority_allocation import PriorityAllocationPolicy
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.safety import effective_caution_tags
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    NormalizedProgramRequest,
    ProgrammedExercise,
    WeeklyVolumePlan,
    WorkoutDay,
)
from app.workouts.program_engine.session_builder import exercise_fits_focus
from app.workouts.program_engine.session_targets import english_session_title
from app.workouts.program_engine.strength_programming import (
    StrengthExerciseRole,
    classify_strength_role,
)
from app.workouts.program_engine.supersets import (
    apply_duration_pressure_superset,
    apply_template_supersets,
)
from app.workouts.program_engine.template_sessions import (
    adaptation_preservation_rank,
    template_removal_rank,
)


def repair_session_durations(
    days: tuple[WorkoutDay, ...],
    request: NormalizedProgramRequest,
    candidates: tuple[ExerciseCandidate, ...],
    ruleset: ProgramRuleset,
    *,
    volume: WeeklyVolumePlan | None = None,
    prefer_acceptable_volume_for_minimum_fill: bool = False,
    session_capacity: SessionCapacity | None = None,
) -> tuple[tuple[WorkoutDay, ...], tuple[str, ...]]:
    """Repair real session estimates while preserving hard program constraints."""

    policy = get_session_duration_policy(request.source.session_duration_minutes)
    resistance_budget = request.source.session_duration_minutes  # pure resistance budget
    repaired: list[WorkoutDay] = []
    reasons: list[str] = []
    for day_index, day in enumerate(days):
        day_capacity = session_capacity
        # -------------------------------------------------------------------
        # Minimum exercises policy:
        #   30-min budget  → allow 3-4 when 5 cannot fit, floor = 3
        #   45+ min budget → minimum 5 (duration alone never lowers this)
        # -------------------------------------------------------------------
        if resistance_budget <= 30:
            # For 30-min sessions, let capacity decide the floor (3–5)
            capacity_floor = (
                max(3, min(5, day_capacity.expected_exercise_count_capacity))
                if day_capacity is not None
                else ruleset.minimum_exercises_per_session
            )
            planned_minimum_exercises = capacity_floor
        else:
            # 45+ min: duration alone MUST NOT reduce below 5
            planned_minimum_exercises = ruleset.minimum_exercises_per_session

        template_adjusted, template_superset_reasons = apply_template_supersets(day.exercises)
        reasons.extend(template_superset_reasons)
        current = _rebuild_day(day, template_adjusted, ruleset)
        other_days = tuple(repaired) + days[day_index + 1 :]

        # ------------------------------------------------------------------
        # Underfill = exercise count below floor ONLY.
        # Being below the time budget is NOT a defect by itself.
        # ------------------------------------------------------------------
        if len(current.exercises) < planned_minimum_exercises:
            reasons.append("SESSION_DURATION_UNDERFILLED")
            current = _repair_underfill(
                current,
                request,
                candidates,
                policy,
                ruleset,
                other_days=other_days,
                volume=volume,
                prefer_acceptable_volume_for_minimum_fill=(
                    prefer_acceptable_volume_for_minimum_fill
                ),
                minimum_exercises=planned_minimum_exercises,
            )

        # ------------------------------------------------------------------
        # Overfill = resistance-only portion exceeds budget + tolerance.
        # (estimated_duration_minutes = warmup + resistance sets;
        #  cardio is added later by add_cardio and is not counted here)
        # ------------------------------------------------------------------
        resistance_minutes = current.estimated_duration_minutes - ruleset.general_warmup_minutes
        if resistance_minutes > policy.maximum_minutes:
            reasons.append("SESSION_DURATION_OVERFILLED")
            current, overfill_reasons = _repair_overfill(
                current,
                request,
                policy,
                ruleset,
                minimum_exercises=planned_minimum_exercises,
            )
            reasons.extend(overfill_reasons)

        # ------------------------------------------------------------------
        # Core-extension allowance
        # ------------------------------------------------------------------
        resistance_after = current.estimated_duration_minutes - ruleset.general_warmup_minutes
        extended_for_core = (
            resistance_after > policy.maximum_minutes
            and resistance_after <= policy.core_preservation_maximum_minutes
            and any(template_removal_rank(item) == 3 for item in current.exercises)
        )

        # ------------------------------------------------------------------
        # Classify outcome
        # ------------------------------------------------------------------
        if resistance_after <= policy.maximum_minutes:
            if current.estimated_duration_minutes != day.estimated_duration_minutes:
                reasons.append("SESSION_DURATION_REPAIR_APPLIED")
            if resistance_after >= policy.minimum_minutes:
                reasons.append("SESSION_DURATION_TARGET_SATISFIED")
            else:
                # Under budget — only a quality issue if program is actually incomplete.
                # Complete programs finishing under budget are acceptable.
                if len(current.exercises) < planned_minimum_exercises:
                    reasons.append("SESSION_DURATION_TARGET_UNSATISFIED")
                    if volume is not None and _duration_shortfall_is_hard_constrained(
                        request, volume
                    ):
                        reasons.append("SESSION_DURATION_CONSTRAINED_BY_HARD_VOLUME_LIMITS")
                    else:
                        reasons.append("SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD")
                else:
                    # Enough exercises; program just finishes under budget.
                    # This is fine — duration is a budget, not a fill target.
                    reasons.append("SESSION_DURATION_TARGET_SATISFIED")
        elif extended_for_core:
            if current.estimated_duration_minutes != day.estimated_duration_minutes:
                reasons.append("SESSION_DURATION_REPAIR_APPLIED")
            reasons.append("SESSION_DURATION_EXTENDED_TO_PRESERVE_CORE")
        else:
            reasons.append("SESSION_DURATION_TARGET_UNSATISFIED")

        repaired.append(current)

    repaired_tuple = _justify_duration_repeats(tuple(repaired))
    return repaired_tuple, tuple(dict.fromkeys(reasons))


def _repair_underfill(
    day: WorkoutDay,
    request: NormalizedProgramRequest,
    candidates: tuple[ExerciseCandidate, ...],
    policy: SessionDurationPolicy,
    ruleset: ProgramRuleset,
    *,
    other_days: tuple[WorkoutDay, ...],
    volume: WeeklyVolumePlan | None,
    prefer_acceptable_volume_for_minimum_fill: bool,
    minimum_exercises: int,
) -> WorkoutDay:
    """Add exercises (or sets) until exercise-count floor is satisfied.

    Rest is NEVER inflated merely to fill unused time — duration is a budget,
    not a fill target.  We stop as soon as the exercise-count floor is met.
    """
    exercises = list(day.exercises)
    while len(exercises) < minimum_exercises:
        # Prefer adding an exercise first, then a set increment as fallback.
        addition = _select_exercise_addition(
            day,
            exercises,
            request,
            candidates,
            policy,
            ruleset,
            other_days=other_days,
            volume=volume,
            prefer_acceptable_volume_for_minimum_fill=(prefer_acceptable_volume_for_minimum_fill),
            minimum_exercises=minimum_exercises,
        )
        if addition is not None:
            exercises.append(addition)
            day = _rebuild_day(day, tuple(exercises), ruleset)
            continue
        # No suitable exercise found — also try a set increment.
        increment = _select_set_increment(
            exercises,
            request,
            policy,
            ruleset,
            other_days=other_days,
            volume=volume,
        )
        if increment is not None:
            index, updated = increment
            exercises[index] = updated
            day = _rebuild_day(day, tuple(exercises), ruleset)
            continue
        # Cannot add more work without violating constraints — stop.
        break
    return day


# _select_rest_extension_for_underfill intentionally removed.
# Inflating rest merely to fill unused session time is prohibited:
# session_duration_minutes is a BUDGET, not a fill target.


def _select_set_increment(
    exercises: list[ProgrammedExercise],
    request: NormalizedProgramRequest,
    policy: SessionDurationPolicy,
    ruleset: ProgramRuleset,
    *,
    other_days: tuple[WorkoutDay, ...],
    volume: WeeklyVolumePlan | None,
) -> tuple[int, ProgrammedExercise] | None:
    if not exercises:
        return None
    options: list[tuple[tuple[object, ...], int, ProgrammedExercise]] = []
    priority_policy = PriorityAllocationPolicy.for_request(request, ruleset)
    weekly_exposures = _weekly_exposure_count((*other_days, _rebuild_day_for_exercises(exercises)))
    for index, exercise in enumerate(exercises):
        if exercise.primary_muscle is None:
            continue
        cap = ruleset.max_working_sets_for_exercise(
            training_status=request.training_status,
            goal=request.primary_goal,
            exercise_type=exercise.exercise_type,
            is_priority=exercise.primary_muscle in priority_policy.priorities,
            weekly_exposure_count=weekly_exposures[exercise.primary_muscle],
            is_primary_strength="STRENGTH_PRIMARY_COMPOUND" in exercise.reason_codes,
        )
        direct_sets = sum(
            item.sets for item in exercises if item.primary_muscle is exercise.primary_muscle
        )
        if exercise.sets >= cap or direct_sets >= ruleset.max_sets_per_muscle_per_session:
            continue
        updated = _with_additional_set(exercise, ruleset)
        simulated = list(exercises)
        simulated[index] = updated
        weekly_before = [item for day in other_days for item in day.exercises] + exercises
        weekly_after = [item for day in other_days for item in day.exercises] + simulated
        if not _acceptable_volume_change(
            weekly_before,
            weekly_after,
            ruleset,
            request,
            volume,
        ):
            continue
        projected = ruleset.general_warmup_minutes + sum(
            item.estimated_minutes for item in simulated
        )
        if projected > policy.maximum_total_minutes(ruleset.general_warmup_minutes):
            continue
        options.append(
            (
                (
                    *priority_policy.precedence_key(exercise.primary_muscle),
                    exercise.sets,
                    direct_sets,
                    str(exercise.exercise_id),
                ),
                index,
                updated,
            )
        )
    if not options:
        return None
    selected = min(options)
    return selected[1], selected[2]


def _select_exercise_addition(
    day: WorkoutDay,
    exercises: list[ProgrammedExercise],
    request: NormalizedProgramRequest,
    candidates: tuple[ExerciseCandidate, ...],
    policy: SessionDurationPolicy,
    ruleset: ProgramRuleset,
    *,
    other_days: tuple[WorkoutDay, ...],
    volume: WeeklyVolumePlan | None,
    prefer_acceptable_volume_for_minimum_fill: bool,
    minimum_exercises: int,
) -> ProgrammedExercise | None:
    if len(exercises) >= ruleset.max_exercises_per_session:
        return None
    existing_ids = {item.exercise_id for item in exercises}
    options = tuple(
        item
        for item in candidates
        if item.id not in existing_ids
        and exercise_fits_focus(item, day.focus)
        and _candidate_is_safe(item, request)
        and ExerciseLabel.CARDIO not in item.labels
    )
    priority_policy = PriorityAllocationPolicy.for_request(request, ruleset)
    ranked = tuple(
        sorted(
            rank_exercises(request, options, ruleset),
            key=lambda item: (
                *priority_policy.precedence_key(item.exercise.primary_muscle),
                -item.score,
                str(item.exercise.id),
            ),
        )
    )
    hard_volume_fallback: ProgrammedExercise | None = None
    for ranked_item in ranked:
        candidate = ranked_item.exercise
        if candidate.primary_muscle is None:
            continue
        direct_sets_for_muscle = sum(
            item.sets for item in exercises if item.primary_muscle is candidate.primary_muscle
        )
        sets = min(
            ruleset.minimum_working_sets,
            ruleset.max_sets_per_muscle_per_session,
            ruleset.max_working_sets_for_exercise(
                training_status=request.training_status,
                goal=request.primary_goal,
                exercise_type=candidate.exercise_type,
                is_priority=candidate.primary_muscle in priority_policy.priorities,
                weekly_exposure_count=1,
                is_primary_strength=False,
            ),
        )
        if sets < 1:
            continue
        if direct_sets_for_muscle + sets > ruleset.max_sets_per_muscle_per_session:
            continue
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
        if (
            ruleset.general_warmup_minutes
            + sum(item.estimated_minutes for item in exercises)
            + estimated
            + (day.cardio.duration_minutes if day.cardio else 0)
            > policy.maximum_total_minutes(ruleset.general_warmup_minutes)
            and len(exercises) >= minimum_exercises
        ):
            continue
        repeated = any(
            item.exercise_id == candidate.id
            for other_day in other_days
            for item in other_day.exercises
        )
        programmed = _program_candidate(
            candidate,
            sets,
            estimated,
            ranked_item.reason_codes,
            prescription,
            ruleset,
            repeated=repeated,
        )
        simulated = [*exercises, programmed]
        other_frequency = sum(
            any(item.primary_muscle is candidate.primary_muscle for item in day.exercises)
            for day in other_days
        )
        training_days = len(other_days) + 1
        frequency_cap = ruleset.maximum_direct_sessions_per_muscle_per_week
        if training_days == 5:
            frequency_cap += 1
        elif training_days >= 6:
            frequency_cap += 2
        if training_days >= 4 and other_frequency + 1 > frequency_cap:
            continue
        weekly_exercises = [item for day in other_days for item in day.exercises] + simulated
        if (
            not prefer_acceptable_volume_for_minimum_fill
            and len(exercises) < minimum_exercises
            and _within_weekly_hard_volume(weekly_exercises, ruleset, request, volume)
        ):
            return simulated[-1]
        if _acceptable_volume_change(
            [item for day in other_days for item in day.exercises] + exercises,
            weekly_exercises,
            ruleset,
            request,
            volume,
        ):
            return simulated[-1]
        if (
            hard_volume_fallback is None
            and len(exercises) < minimum_exercises
            and _within_weekly_hard_volume(weekly_exercises, ruleset, request, volume)
        ):
            hard_volume_fallback = simulated[-1]
    return hard_volume_fallback


def _programmed_strength_role(exercise: ProgrammedExercise) -> StrengthExerciseRole:
    if "STRENGTH_PRIMARY_COMPOUND" in exercise.reason_codes:
        return StrengthExerciseRole.PRIMARY_STRENGTH
    if "STRENGTH_SECONDARY_COMPOUND" in exercise.reason_codes:
        return StrengthExerciseRole.SECONDARY_COMPOUND
    return StrengthExerciseRole.ACCESSORY


def _duration_shortfall_is_hard_constrained(
    request: NormalizedProgramRequest,
    volume: WeeklyVolumePlan,
) -> bool:
    return bool(
        set(volume.reason_codes).intersection(
            {
                "VOLUME_REDUCED_FOR_RECOVERY",
                "VOLUME_REDUCED_FOR_TIME_LIMIT",
                "VOLUME_CAPPED_FOR_SPLIT_FREQUENCY",
                "VOLUME_CAPPED_FOR_PREVIOUS_EFFECTIVE_VOLUME",
                "VOLUME_CAPPED_FOR_PREVIOUS_VOLUME",
            }
        )
        or request.constraints.blocked_exercises
        or request.constraints.blocked_movement_patterns
        or request.constraints.blocked_caution_tags
        or request.constraints.allowed_range_of_motion
        or request.resistance_training_days >= 5
    )


def _repair_overfill(
    day: WorkoutDay,
    request: NormalizedProgramRequest,
    policy: SessionDurationPolicy,
    ruleset: ProgramRuleset,
    *,
    minimum_exercises: int,
) -> tuple[WorkoutDay, tuple[str, ...]]:
    exercises = list(day.exercises)
    reasons: list[str] = []
    priority_policy = PriorityAllocationPolicy.for_request(request, ruleset)
    while day.estimated_duration_minutes > policy.maximum_total_minutes(
        ruleset.general_warmup_minutes
    ):
        low_value_removable = [
            (index, item)
            for index, item in enumerate(exercises)
            if len(exercises) > minimum_exercises
            and not any(code.startswith("REQUIRED_") for code in item.reason_codes)
            and template_removal_rank(item) < 3
            and priority_policy.preservation_rank(item.primary_muscle) == 0
            and (
                template_removal_rank(item) in {0, 1}
                or "SESSION_SIZE_ACCESSORY" in item.reason_codes
            )
        ]
        if low_value_removable:
            index, _ = min(
                low_value_removable,
                key=lambda pair: (
                    adaptation_preservation_rank(pair[1], priority_policy),
                    -pair[1].estimated_minutes,
                    str(pair[1].exercise_id),
                ),
            )
            exercises.pop(index)
            day = _rebuild_day(day, tuple(exercises), ruleset)
            continue
        options = [
            (index, item)
            for index, item in enumerate(exercises)
            if item.sets > ruleset.minimum_working_sets
            and not any(code.startswith("REQUIRED_") for code in item.reason_codes)
            and template_removal_rank(item) < 3
            and priority_policy.preservation_rank(item.primary_muscle) == 0
        ]
        if options:
            index, item = min(
                options,
                key=lambda pair: (
                    adaptation_preservation_rank(pair[1], priority_policy),
                    "SESSION_SIZE_ACCESSORY" not in pair[1].reason_codes,
                    pair[1].sets,
                    -pair[1].estimated_minutes,
                    str(pair[1].exercise_id),
                ),
            )
            exercises[index] = _with_fewer_sets(item, ruleset)
            day = _rebuild_day(day, tuple(exercises), ruleset)
            continue
        removable = [
            (index, item)
            for index, item in enumerate(exercises)
            if len(exercises) > minimum_exercises
            and not any(code.startswith("REQUIRED_") for code in item.reason_codes)
            and template_removal_rank(item) < 3
            and priority_policy.preservation_rank(item.primary_muscle) == 0
        ]
        if not removable:
            supersetted, superset_reasons = apply_duration_pressure_superset(
                tuple(exercises), request, ruleset
            )
            if superset_reasons:
                exercises = list(supersetted)
                reasons.extend(superset_reasons)
                day = _rebuild_day(day, tuple(exercises), ruleset)
                continue
            rest_reduction = _select_rest_reduction_for_overfill(
                exercises,
                request,
                priority_policy,
                ruleset,
            )
            if rest_reduction is None:
                break
            index, updated = rest_reduction
            exercises[index] = updated
            day = _rebuild_day(day, tuple(exercises), ruleset)
            continue
        index, _ = min(
            removable,
            key=lambda pair: (
                adaptation_preservation_rank(pair[1], priority_policy),
                "SESSION_SIZE_ACCESSORY" not in pair[1].reason_codes,
                -pair[1].estimated_minutes,
                str(pair[1].exercise_id),
            ),
        )
        exercises.pop(index)
        day = _rebuild_day(day, tuple(exercises), ruleset)
    return day, tuple(dict.fromkeys(reasons))


def _select_rest_reduction_for_overfill(
    exercises: list[ProgrammedExercise],
    request: NormalizedProgramRequest,
    priority_policy: PriorityAllocationPolicy,
    ruleset: ProgramRuleset,
) -> tuple[int, ProgrammedExercise] | None:
    options: list[tuple[int, int, int, str, int, ProgrammedExercise]] = []
    for index, exercise in enumerate(exercises):
        minimum_rest = _duration_repair_minimum_rest(exercise, request, ruleset)
        if exercise.rest_seconds <= minimum_rest:
            continue
        rest_seconds = max(
            minimum_rest,
            exercise.rest_seconds - ruleset.duration_repair_rest_increment_seconds,
        )
        updated = replace(
            exercise,
            rest_seconds=rest_seconds,
            estimated_minutes=_estimate_preserving_time_saving(
                exercise,
                sets=exercise.sets,
                rest_seconds=rest_seconds,
                ruleset=ruleset,
            ),
            reason_codes=tuple(
                dict.fromkeys(exercise.reason_codes + ("ACCESSORY_REST_REDUCED_FOR_DURATION",))
            ),
        )
        options.append(
            (
                adaptation_preservation_rank(exercise, priority_policy),
                exercise.exercise_type is not ExerciseType.ISOLATION,
                -exercise.rest_seconds,
                str(exercise.exercise_id),
                index,
                updated,
            )
        )
    if not options:
        return None
    selected = min(options)
    return selected[4], selected[5]


def _duration_repair_minimum_rest(
    exercise: ProgrammedExercise,
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
) -> int:
    return prescription_for(
        request.primary_goal,
        exercise.exercise_type,
        request.training_status,
        ruleset,
        prescription_mode=exercise.prescription_mode,
        duration_min_seconds=exercise.duration_min_seconds,
        duration_max_seconds=exercise.duration_max_seconds,
        strength_role=(
            _programmed_strength_role(exercise) if request.primary_goal is Goal.STRENGTH else None
        ),
    ).minimum_rest_seconds


def _program_candidate(
    candidate: ExerciseCandidate,
    sets: int,
    estimated: int,
    ranked_reasons: tuple[str, ...],
    prescription: ExercisePrescription,
    ruleset: ProgramRuleset,
    *,
    repeated: bool = False,
) -> ProgrammedExercise:
    return ProgrammedExercise(
        exercise_id=candidate.id,
        exercise_name=candidate.name,
        order=1,
        sets=sets,
        rep_min=prescription.rep_min,
        rep_max=prescription.rep_max,
        target_rir=prescription.target_rir,
        rest_seconds=prescription.rest_seconds,
        estimated_minutes=estimated,
        reason_codes=(
            *ranked_reasons,
            *(("CORE_MOVEMENT_REPEATED_FOR_PROGRESSION",) if repeated else ()),
            "SESSION_SIZE_ACCESSORY",
            "SESSION_DURATION_REPAIR_APPLIED",
        ),
        prescription_mode=prescription.mode,
        duration_min_seconds=prescription.duration_min_seconds,
        duration_max_seconds=prescription.duration_max_seconds,
        movement_pattern=candidate.movement_pattern,
        primary_muscle=candidate.primary_muscle,
        secondary_muscles=candidate.secondary_muscles,
        equipment=candidate.equipment,
        caution_tags=candidate.caution_tags,
        range_of_motion_profile=candidate.range_of_motion_profile,
        impact_level=candidate.impact_level,
        axial_loading_level=candidate.axial_loading_level,
        stability_demand=candidate.stability_demand,
        is_active=candidate.is_active,
        is_programmable=candidate.is_programmable,
        needs_review=candidate.needs_review,
        exercise_type=candidate.exercise_type,
        counts_toward_volume=True,
    )


def _with_additional_set(
    exercise: ProgrammedExercise, ruleset: ProgramRuleset
) -> ProgrammedExercise:
    sets = exercise.sets + 1
    return replace(
        exercise,
        sets=sets,
        estimated_minutes=_estimate_preserving_time_saving(
            exercise,
            sets=sets,
            rest_seconds=exercise.rest_seconds,
            ruleset=ruleset,
        ),
        reason_codes=exercise.reason_codes + ("SESSION_DURATION_REPAIR_APPLIED",),
    )


def _with_fewer_sets(exercise: ProgrammedExercise, ruleset: ProgramRuleset) -> ProgrammedExercise:
    sets = exercise.sets - 1
    return replace(
        exercise,
        sets=sets,
        estimated_minutes=_estimate_preserving_time_saving(
            exercise,
            sets=sets,
            rest_seconds=exercise.rest_seconds,
            ruleset=ruleset,
        ),
        reason_codes=exercise.reason_codes + ("SESSION_DURATION_REPAIR_APPLIED",),
    )


def _candidate_is_safe(candidate: ExerciseCandidate, request: NormalizedProgramRequest) -> bool:
    return (
        candidate.is_active
        and candidate.is_programmable
        and not candidate.needs_review
        and candidate.id not in request.constraints.blocked_exercises
        and candidate.movement_pattern not in request.constraints.blocked_movement_patterns
        and not effective_caution_tags(candidate).intersection(
            request.constraints.blocked_caution_tags
        )
        and effective_required_equipment(candidate.equipment, candidate.movement_pattern).issubset(
            request.constraints.available_equipment
        )
    )


def _estimate_preserving_time_saving(
    exercise: ProgrammedExercise,
    *,
    sets: int,
    rest_seconds: int,
    ruleset: ProgramRuleset,
) -> int:
    straight_before = estimate_exercise_minutes(
        exercise.sets,
        exercise.rest_seconds,
        exercise.warmup_sets,
        ruleset,
    )
    existing_saving = (
        max(0, straight_before - exercise.estimated_minutes)
        if "SAFE_SUPERSET_DURATION_SAVING" in exercise.reason_codes
        else 0
    )
    straight_after = estimate_exercise_minutes(
        sets,
        rest_seconds,
        exercise.warmup_sets,
        ruleset,
    )
    return max(1, straight_after - existing_saving)


def _within_weekly_hard_volume(
    exercises: list[ProgrammedExercise],
    ruleset: ProgramRuleset,
    request: NormalizedProgramRequest,
    volume: WeeklyVolumePlan | None,
) -> bool:
    effective = calculate_effective_volume(exercises, ruleset)
    maximum = ruleset.maximum_sets[request.training_status]
    if any(value > maximum for value in effective.effective_sets_by_muscle.values()):
        return False
    if volume is None:
        return True
    return all(
        effective.effective_sets_by_muscle.get(target.muscle.value, 0) <= target.maximum_hard
        for target in volume.targets
    )


def _within_weekly_acceptable_volume(
    exercises: list[ProgrammedExercise],
    ruleset: ProgramRuleset,
    request: NormalizedProgramRequest,
    volume: WeeklyVolumePlan | None,
) -> bool:
    if not _within_weekly_hard_volume(exercises, ruleset, request, volume):
        return False
    if volume is None:
        return True
    effective = calculate_effective_volume(exercises, ruleset)
    return all(
        effective.effective_sets_by_muscle.get(target.muscle.value, 0) <= target.acceptable_maximum
        for target in volume.targets
    )


def _acceptable_volume_change(
    before: list[ProgrammedExercise],
    after: list[ProgrammedExercise],
    ruleset: ProgramRuleset,
    request: NormalizedProgramRequest,
    volume: WeeklyVolumePlan | None,
) -> bool:
    if not _within_weekly_hard_volume(after, ruleset, request, volume):
        return False
    if volume is None:
        return True
    before_effective = calculate_effective_volume(before, ruleset)
    after_effective = calculate_effective_volume(after, ruleset)
    return all(
        after_effective.effective_sets_by_muscle.get(target.muscle.value, 0)
        <= target.acceptable_maximum
        or after_effective.effective_sets_by_muscle.get(target.muscle.value, 0)
        <= before_effective.effective_sets_by_muscle.get(target.muscle.value, 0)
        for target in volume.targets
    )


def _within_weekly_minimum_volume(
    exercises: list[ProgrammedExercise],
    ruleset: ProgramRuleset,
    volume: WeeklyVolumePlan | None,
) -> bool:
    if volume is None:
        return True
    effective = calculate_effective_volume(exercises, ruleset)
    return all(
        (
            not target.direct_minimum_required
            or effective.direct_sets_by_muscle.get(target.muscle.value, 0)
            >= target.minimum_direct_sets
        )
        and (
            not target.minimum_coverage_required
            or effective.effective_sets_by_muscle.get(target.muscle.value, 0)
            >= target.minimum_effective_sets
        )
        for target in volume.targets
    )


def _justify_duration_repeats(days: tuple[WorkoutDay, ...]) -> tuple[WorkoutDay, ...]:
    duration_repaired_ids = {
        item.exercise_id
        for day in days
        for item in day.exercises
        if "SESSION_DURATION_REPAIR_APPLIED" in item.reason_codes
    }
    seen: set[object] = set()
    updated_days: list[WorkoutDay] = []
    for day in days:
        exercises: list[ProgrammedExercise] = []
        for item in day.exercises:
            if item.exercise_id in duration_repaired_ids and item.exercise_id in seen:
                item = replace(
                    item,
                    reason_codes=tuple(
                        dict.fromkeys(
                            item.reason_codes + ("CORE_MOVEMENT_REPEATED_FOR_PROGRESSION",)
                        )
                    ),
                )
            seen.add(item.exercise_id)
            exercises.append(item)
        updated_days.append(replace(day, exercises=tuple(exercises)))
    return tuple(updated_days)


def _weekly_exposure_count(days: tuple[WorkoutDay, ...]) -> Counter[MuscleGroup]:
    return Counter(
        muscle
        for day in days
        for muscle in {
            item.primary_muscle for item in day.exercises if item.primary_muscle is not None
        }
    )


def _rebuild_day_for_exercises(exercises: list[ProgrammedExercise]) -> WorkoutDay:
    return WorkoutDay(
        day_index=0,
        weekday=None,
        title="",
        focus="",
        estimated_duration_minutes=0,
        exercises=tuple(exercises),
    )


def _rebuild_day(
    original: WorkoutDay,
    exercises: tuple[ProgrammedExercise, ...],
    ruleset: ProgramRuleset,
) -> WorkoutDay:
    ordered = tuple(replace(item, order=index + 1) for index, item in enumerate(exercises))
    return replace(
        original,
        exercises=ordered,
        title=english_session_title(original.day_index, ordered),
        estimated_duration_minutes=(
            ruleset.general_warmup_minutes
            + sum(item.estimated_minutes for item in ordered)
            + (original.cardio.duration_minutes if original.cardio else 0)
        ),
    )
