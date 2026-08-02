from collections import Counter
from dataclasses import replace

from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.prescription import estimate_exercise_minutes
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import (
    NormalizedProgramRequest,
    ProgrammedExercise,
    WeeklyVolumePlan,
    WorkoutDay,
)


def repair_weekly_volume(
    days: tuple[WorkoutDay, ...],
    request: NormalizedProgramRequest,
    volume: WeeklyVolumePlan,
    ruleset: ProgramRuleset,
) -> tuple[tuple[WorkoutDay, ...], tuple[str, ...]]:
    """Keep direct volume inside hard caps before final validation.

    The deterministic repair prefers reducing later, non-priority accessories.
    It never removes the only exposure of a muscle in the current week.
    """
    repaired = [list(day.exercises) for day in days]
    hard_maximums = {
        target.muscle: target.maximum_hard for target in volume.targets
    }
    reasons: list[str] = []
    while True:
        direct = _direct_sets(repaired)
        excessive = {
            muscle
            for muscle, sets in direct.items()
            if sets > hard_maximums.get(
                muscle,
                ruleset.maximum_sets[request.training_status],
            )
        }
        if not excessive:
            break
        candidates = [
            (day_index, exercise_index, exercise)
            for day_index, exercises in enumerate(repaired)
            for exercise_index, exercise in enumerate(exercises)
            if exercise.primary_muscle in excessive and exercise.counts_toward_volume
        ]
        if not candidates:
            break
        day_index, exercise_index, exercise = min(
            candidates,
            key=lambda candidate: (
                candidate[2].primary_muscle in request.source.priority_muscles,
                -candidate[0],
                -candidate[2].order,
                str(candidate[2].exercise_id),
            ),
        )
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
        if same_muscle_exposures <= 1:
            break
        repaired[day_index].pop(exercise_index)
        reasons.append("VOLUME_REPAIR_REMOVED_REDUNDANT_EXERCISE")

    return _rebuild_days(days, repaired, ruleset), tuple(dict.fromkeys(reasons))


def _direct_sets(days: list[list[ProgrammedExercise]]) -> Counter[MuscleGroup]:
    return Counter(
        item.primary_muscle
        for exercises in days
        for item in exercises
        if item.primary_muscle is not None and item.counts_toward_volume
        for _ in range(item.sets)
    )


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
                ),
            )
        )
    return tuple(repaired_days)
