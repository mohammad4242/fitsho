from collections import Counter
from dataclasses import replace

from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.effective_volume import calculate_effective_volume
from app.workouts.program_engine.prescription import estimate_exercise_minutes
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    NormalizedProgramRequest,
    ProgrammedExercise,
    VolumeTarget,
    WeeklyVolumePlan,
    WorkoutDay,
)


def repair_weekly_volume(
    days: tuple[WorkoutDay, ...],
    request: NormalizedProgramRequest,
    volume: WeeklyVolumePlan,
    ruleset: ProgramRuleset,
) -> tuple[tuple[WorkoutDay, ...], tuple[str, ...]]:
    """Keep effective volume inside targets and hard caps before validation.

    The deterministic repair first removes excess volume, then adds sets only
    when effective or required direct volume is still below its target.
    """
    repaired = [list(day.exercises) for day in days]
    targets = {target.muscle: target for target in volume.targets}
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
        per_session_excessive = _per_session_excessive(repaired, ruleset)
        reduction = _select_reduction_candidate(
            repaired,
            weekly_excessive,
            per_session_excessive,
            direct,
            targets,
            request,
            ruleset,
        )
        if reduction is not None:
            day_index, exercise_index, exercise = reduction
            if exercise.sets > ruleset.minimum_working_sets:
                repaired[day_index][exercise_index] = replace(
                    exercise,
                    sets=exercise.sets - 1,
                    estimated_minutes=estimate_exercise_minutes(
                        exercise.sets - 1,
                        exercise.rest_seconds,
                        exercise.warmup_sets,
                        ruleset,
                    ),
                    reason_codes=exercise.reason_codes + ("VOLUME_REPAIR_REDUCED_SET",),
                )
                reasons.append("VOLUME_REPAIR_REDUCED_SET")
                continue
            same_muscle_exposures = sum(
                1
                for exercises in repaired
                for item in exercises
                if item.primary_muscle is exercise.primary_muscle and item.counts_toward_volume
            )
            if same_muscle_exposures > 1:
                repaired[day_index].pop(exercise_index)
                reasons.append("VOLUME_REPAIR_REMOVED_REDUNDANT_EXERCISE")
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
        addition = _select_addition_candidate(
            repaired,
            direct_under,
            effective_under,
            direct,
            targets,
            tuple(day.cardio.duration_minutes if day.cardio else 0 for day in days),
            request,
            ruleset,
        )
        if addition is None:
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

    return _rebuild_days(days, repaired, ruleset), tuple(dict.fromkeys(reasons))


def _maximum_for(
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
) -> tuple[int, int, ProgrammedExercise] | None:
    candidates = []
    for day_index, exercises in enumerate(days):
        for exercise_index, exercise in enumerate(exercises):
            if not exercise.counts_toward_volume or exercise.primary_muscle is None:
                continue
            affected = {exercise.primary_muscle.value} | {
                muscle.value for muscle in exercise.secondary_muscles
            }
            if (
                not affected.intersection(weekly_excessive)
                and (
                    day_index,
                    exercise.primary_muscle,
                )
                not in per_session_excessive
            ):
                continue
            minimum_direct = targets.get(exercise.primary_muscle)
            if (
                minimum_direct is not None
                and direct[exercise.primary_muscle.value] - 1 < minimum_direct.minimum_direct_sets
            ):
                continue
            if exercise.sets <= ruleset.minimum_working_sets:
                continue
            candidates.append((day_index, exercise_index, exercise))
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda candidate: (
            candidate[2].primary_muscle in request.source.priority_muscles,
            -candidate[0],
            -candidate[2].order,
            str(candidate[2].exercise_id),
        ),
    )


def _select_addition_candidate(
    days: list[list[ProgrammedExercise]],
    direct_under: set[MuscleGroup],
    effective_under: set[MuscleGroup],
    weekly_direct: Counter[str],
    targets: dict[MuscleGroup, VolumeTarget],
    cardio_minutes_by_day: tuple[int, ...],
    request: NormalizedProgramRequest,
    ruleset: ProgramRuleset,
) -> tuple[int, int, ProgrammedExercise, str] | None:
    candidates = []
    hard_maximums = {muscle.value: target.maximum_hard for muscle, target in targets.items()}
    for day_index, exercises in enumerate(days):
        direct_by_session = _direct_sets([exercises])
        for exercise_index, exercise in enumerate(exercises):
            if not exercise.counts_toward_volume or exercise.primary_muscle is None:
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
                exercises, exercise, updated, cardio_minutes_by_day[day_index], ruleset
            ) > (request.source.session_duration_minutes + ruleset.duration_tolerance_minutes):
                continue
            simulated = [list(day_exercises) for day_exercises in days]
            simulated[day_index][exercise_index] = updated
            simulated_volume = calculate_effective_volume(
                (item for items in simulated for item in items),
                ruleset,
            )
            if any(
                simulated_volume.effective_sets_by_muscle.get(muscle, 0) > maximum
                for muscle, maximum in hard_maximums.items()
            ):
                continue
            reason = (
                "VOLUME_REPAIR_ADDED_SET_FOR_DIRECT_MINIMUM"
                if direct_needs
                else "VOLUME_REPAIR_ADDED_SET_FOR_EFFECTIVE_TARGET"
            )
            candidates.append(
                (
                    0 if direct_needs else 1,
                    0 if primary in effective_under else 1,
                    day_index,
                    exercise_index,
                    exercise,
                    reason,
                )
            )
    if not candidates:
        return None
    _, _, day_index, exercise_index, exercise, reason = min(
        candidates,
        key=lambda candidate: (
            candidate[0],
            candidate[1],
            candidate[2],
            candidate[3],
            str(candidate[4].exercise_id),
        ),
    )
    return day_index, exercise_index, exercise, reason


def _direct_sets(days: list[list[ProgrammedExercise]]) -> Counter[MuscleGroup]:
    return Counter(
        item.primary_muscle
        for exercises in days
        for item in exercises
        if item.primary_muscle is not None and item.counts_toward_volume
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
    cardio_minutes: int,
    ruleset: ProgramRuleset,
) -> int:
    total = sum(item.estimated_minutes for item in original_exercises)
    total += updated.estimated_minutes - original.estimated_minutes
    return ruleset.general_warmup_minutes + total + cardio_minutes
