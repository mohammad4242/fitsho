from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class ExerciseTiming:
    sets: int
    rest_seconds: int


@dataclass(frozen=True)
class WorkoutGenerationPolicy:
    session_duration_minutes: int
    warmup_minutes: int
    maximum_exercises_per_day: int
    minimum_sets: int = 2
    maximum_sets: int = 5
    minimum_repetitions: int = 5
    maximum_repetitions: int = 20
    allowed_rest_seconds: tuple[int, ...] = (45, 60, 75, 90, 120, 150, 180)
    allowed_rir: tuple[int, ...] = (1, 2, 3, 4)
    set_execution_seconds: int = 45
    transition_seconds_per_exercise: int = 90

    @classmethod
    def for_session_duration(
        cls,
        session_duration_minutes: int,
        *,
        warmup_minutes: int = 5,
    ) -> WorkoutGenerationPolicy:
        maximums = {30: 3, 45: 4, 60: 6, 75: 7, 90: 8}
        return cls(
            session_duration_minutes=session_duration_minutes,
            warmup_minutes=warmup_minutes,
            maximum_exercises_per_day=maximums[session_duration_minutes],
        )


def calculate_exercise_minutes(
    timing: ExerciseTiming,
    *,
    set_execution_seconds: int = 45,
    transition_seconds: int = 90,
) -> int:
    total_seconds = (
        transition_seconds
        + timing.sets * set_execution_seconds
        + max(timing.sets - 1, 0) * timing.rest_seconds
    )
    return ceil(total_seconds / 60)


def calculate_day_minutes(
    exercises: Iterable[ExerciseTiming],
    *,
    set_execution_seconds: int = 45,
    transition_seconds: int = 90,
) -> int:
    return sum(
        calculate_exercise_minutes(
            exercise,
            set_execution_seconds=set_execution_seconds,
            transition_seconds=transition_seconds,
        )
        for exercise in exercises
    )


def fits_session_duration(
    exercises: Iterable[ExerciseTiming],
    policy: WorkoutGenerationPolicy,
) -> bool:
    return (
        policy.warmup_minutes
        + calculate_day_minutes(
            exercises,
            set_execution_seconds=policy.set_execution_seconds,
            transition_seconds=policy.transition_seconds_per_exercise,
        )
        <= policy.session_duration_minutes
    )
