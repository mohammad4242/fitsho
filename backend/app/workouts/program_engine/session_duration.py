from collections import Counter
from dataclasses import replace

from app.exercises.enums import ExerciseLabel, MuscleGroup
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
from app.workouts.program_engine.strength_programming import classify_strength_role


def repair_session_durations(
    days: tuple[WorkoutDay, ...],
    request: NormalizedProgramRequest,
    candidates: tuple[ExerciseCandidate, ...],
    ruleset: ProgramRuleset,
    *,
    volume: WeeklyVolumePlan | None = None,
) -> tuple[tuple[WorkoutDay, ...], tuple[str, ...]]:
    """Repair real session estimates while preserving hard program constraints."""

    policy = get_session_duration_policy(request.source.session_duration_minutes)
    repaired: list[WorkoutDay] = []
    reasons: list[str] = []
    for day_index, day in enumerate(days):
        current = _rebuild_day(day, day.exercises, ruleset)
        other_days = tuple(repaired) + days[day_index + 1 :]
        if current.estimated_duration_minutes < policy.minimum_minutes:
            reasons.append("SESSION_DURATION_UNDERFILLED")
            current = _repair_underfill(
                current,
                request,
                candidates,
                policy,
                ruleset,
                other_days=other_days,
                volume=volume,
            )
        if current.estimated_duration_minutes > policy.maximum_minutes:
            reasons.append("SESSION_DURATION_OVERFILLED")
            current = _repair_overfill(current, request, policy, ruleset)
        if policy.contains(current.estimated_duration_minutes):
            if current.estimated_duration_minutes != day.estimated_duration_minutes:
                reasons.append("SESSION_DURATION_REPAIR_APPLIED")
            reasons.append("SESSION_DURATION_TARGET_SATISFIED")
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
) -> WorkoutDay:
    exercises = list(day.exercises)
    while day.estimated_duration_minutes < policy.minimum_minutes:
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
        addition = _select_exercise_addition(
            day,
            exercises,
            request,
            candidates,
            policy,
            ruleset,
            other_days=other_days,
            volume=volume,
        )
        if addition is None:
            untracked_increment = _select_untracked_set_increment(
                exercises,
                request,
                policy,
                ruleset,
                other_days=other_days,
                volume=volume,
            )
            if untracked_increment is None:
                break
            index, updated = untracked_increment
            exercises[index] = updated
            day = _rebuild_day(day, tuple(exercises), ruleset)
            continue
        exercises.append(addition)
        day = _rebuild_day(day, tuple(exercises), ruleset)
    return day


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
    options: list[tuple[int, int, int, str, int, ProgrammedExercise]] = []
    weekly_exposures = _weekly_exposure_count((*other_days, _rebuild_day_for_exercises(exercises)))
    for index, exercise in enumerate(exercises):
        if exercise.primary_muscle is None or not exercise.counts_toward_volume:
            continue
        cap = ruleset.max_working_sets_for_exercise(
            training_status=request.training_status,
            goal=request.primary_goal,
            exercise_type=exercise.exercise_type,
            is_priority=exercise.primary_muscle in request.source.priority_muscles,
            weekly_exposure_count=weekly_exposures[exercise.primary_muscle],
            is_primary_strength="STRENGTH_PRIMARY_COMPOUND" in exercise.reason_codes,
        )
        direct_sets = sum(
            item.sets
            for item in exercises
            if item.primary_muscle is exercise.primary_muscle and item.counts_toward_volume
        )
        if exercise.sets >= cap or direct_sets >= ruleset.max_sets_per_muscle_per_session:
            continue
        updated = _with_additional_set(exercise, ruleset)
        simulated = list(exercises)
        simulated[index] = updated
        if not _within_weekly_hard_volume(
            [item for day in other_days for item in day.exercises] + simulated,
            ruleset,
            request,
            volume,
        ):
            continue
        projected = ruleset.general_warmup_minutes + sum(
            item.estimated_minutes for item in simulated
        )
        if projected > policy.maximum_minutes:
            continue
        options.append(
            (
                0 if exercise.primary_muscle in request.source.priority_muscles else 1,
                exercise.sets,
                direct_sets,
                str(exercise.exercise_id),
                index,
                updated,
            )
        )
    if not options:
        return None
    selected = min(options)
    return selected[4], selected[5]


def _select_untracked_set_increment(
    exercises: list[ProgrammedExercise],
    request: NormalizedProgramRequest,
    policy: SessionDurationPolicy,
    ruleset: ProgramRuleset,
    *,
    other_days: tuple[WorkoutDay, ...],
    volume: WeeklyVolumePlan | None,
) -> tuple[int, ProgrammedExercise] | None:
    options: list[tuple[int, int, str, int, ProgrammedExercise]] = []
    exposures = _weekly_exposure_count((*other_days, _rebuild_day_for_exercises(exercises)))
    for index, exercise in enumerate(exercises):
        if (
            exercise.primary_muscle is None
            or exercise.counts_toward_volume
            or exercise.primary_muscle in request.source.priority_muscles
            or exercise.sets < ruleset.minimum_working_sets
            or any(code.startswith("REQUIRED_") for code in exercise.reason_codes)
        ):
            continue
        cap = ruleset.max_working_sets_for_exercise(
            training_status=request.training_status,
            goal=request.primary_goal,
            exercise_type=exercise.exercise_type,
            is_priority=False,
            weekly_exposure_count=exposures[exercise.primary_muscle],
            is_primary_strength="STRENGTH_PRIMARY_COMPOUND" in exercise.reason_codes,
        )
        if exercise.sets >= cap:
            continue
        updated = replace(
            _with_additional_set(exercise, ruleset),
            counts_toward_volume=False,
            reason_codes=exercise.reason_codes
            + ("SESSION_SIZE_ACCESSORY", "SESSION_DURATION_REPAIR_APPLIED"),
        )
        projected = (
            ruleset.general_warmup_minutes
            + sum(
                item.estimated_minutes
                for item_index, item in enumerate(exercises)
                if item_index != index
            )
            + updated.estimated_minutes
        )
        if projected > policy.maximum_minutes:
            continue
        options.append(
            (exercise.sets, exercise.estimated_minutes, str(exercise.exercise_id), index, updated)
        )
    if not options:
        return None
    selected = min(options)
    return selected[3], selected[4]


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
    ranked = rank_exercises(request, options, ruleset)
    for ranked_item in ranked:
        candidate = ranked_item.exercise
        if candidate.primary_muscle is None:
            continue
        sets = min(
            ruleset.minimum_working_sets,
            ruleset.max_sets_per_muscle_per_session,
            ruleset.max_working_sets_for_exercise(
                training_status=request.training_status,
                goal=request.primary_goal,
                exercise_type=candidate.exercise_type,
                is_priority=candidate.primary_muscle in request.source.priority_muscles,
                weekly_exposure_count=1,
                is_primary_strength=False,
            ),
        )
        if sets < 1:
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
            > policy.maximum_minutes
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
        if programmed.counts_toward_volume and not _within_weekly_hard_volume(
            [item for day in other_days for item in day.exercises] + simulated,
            ruleset,
            request,
            volume,
        ):
            continue
        other_frequency = sum(
            any(item.primary_muscle is candidate.primary_muscle for item in day.exercises)
            for day in other_days
        )
        if (
            programmed.counts_toward_volume
            and len(other_days) + 1 >= 4
            and other_frequency
            + int(any(item.primary_muscle is candidate.primary_muscle for item in exercises))
            > ruleset.maximum_direct_sessions_per_muscle_per_week
        ):
            continue
        return simulated[-1]
    return None


def _repair_overfill(
    day: WorkoutDay,
    request: NormalizedProgramRequest,
    policy: SessionDurationPolicy,
    ruleset: ProgramRuleset,
) -> WorkoutDay:
    exercises = list(day.exercises)
    while day.estimated_duration_minutes > policy.maximum_minutes:
        options = [
            (index, item)
            for index, item in enumerate(exercises)
            if item.primary_muscle not in request.source.priority_muscles
            and item.sets > ruleset.minimum_working_sets
            and not any(code.startswith("REQUIRED_") for code in item.reason_codes)
        ]
        if options:
            index, item = min(
                options,
                key=lambda pair: (
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
            if len(exercises) > ruleset.minimum_exercises_per_session
            and item.primary_muscle not in request.source.priority_muscles
            and not any(code.startswith("REQUIRED_") for code in item.reason_codes)
        ]
        if not removable:
            break
        index, _ = min(
            removable,
            key=lambda pair: (
                "SESSION_SIZE_ACCESSORY" not in pair[1].reason_codes,
                -pair[1].estimated_minutes,
                str(pair[1].exercise_id),
            ),
        )
        exercises.pop(index)
        day = _rebuild_day(day, tuple(exercises), ruleset)
    return day


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
        counts_toward_volume=False,
    )


def _with_additional_set(
    exercise: ProgrammedExercise, ruleset: ProgramRuleset
) -> ProgrammedExercise:
    sets = exercise.sets + 1
    return replace(
        exercise,
        sets=sets,
        estimated_minutes=estimate_exercise_minutes(
            sets, exercise.rest_seconds, exercise.warmup_sets, ruleset
        ),
        reason_codes=exercise.reason_codes + ("SESSION_DURATION_REPAIR_APPLIED",),
    )


def _with_fewer_sets(exercise: ProgrammedExercise, ruleset: ProgramRuleset) -> ProgrammedExercise:
    sets = exercise.sets - 1
    return replace(
        exercise,
        sets=sets,
        estimated_minutes=estimate_exercise_minutes(
            sets, exercise.rest_seconds, exercise.warmup_sets, ruleset
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
        effective.effective_sets_by_muscle.get(target.muscle.value, 0)
        <= target.maximum_hard + round(target.maximum_hard * ruleset.secondary_set_credit)
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
                    reason_codes=item.reason_codes + ("CORE_MOVEMENT_REPEATED_FOR_PROGRESSION",),
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
            item.primary_muscle
            for item in day.exercises
            if item.primary_muscle is not None and item.counts_toward_volume
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
