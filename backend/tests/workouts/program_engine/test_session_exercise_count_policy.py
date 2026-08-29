from types import SimpleNamespace

import pytest

from app.exercises.enums import ExerciseType, MuscleGroup
from app.workouts.program_engine.duration_policy import (
    calculate_total_session_minutes_from_exercises,
    get_session_exercise_count_policy,
)
from app.workouts.program_engine.supplemental_policy import (
    exercise_count_breakdown,
    main_exercise_count,
)


def test_core_is_never_counted_as_main_when_primary_muscle_is_non_supplemental() -> None:
    core = SimpleNamespace(
        exercise_type=ExerciseType.CORE,
        primary_muscle=MuscleGroup.CHEST,
    )

    assert main_exercise_count((core,)) == 0


@pytest.mark.parametrize(
    ("duration", "minimum", "maximum"),
    (
        (30, 3, 4),
        (45, 5, 9),
        (60, 5, 9),
        (75, 5, 9),
        (90, 5, 9),
        (120, 5, 9),
    ),
)
def test_session_exercise_count_policy_covers_supported_duration_matrix(
    duration: int,
    minimum: int,
    maximum: int,
) -> None:
    policy = get_session_exercise_count_policy(duration)

    assert (policy.minimum_main_exercises, policy.maximum_main_exercises) == (minimum, maximum)
    assert [policy.contains(count) for count in (minimum - 1, minimum, maximum, maximum + 1)] == [
        False,
        True,
        True,
        False,
    ]


def test_count_breakdown_uses_structured_metadata_across_nested_wrappers() -> None:
    main = SimpleNamespace(
        name="Core Crusher",
        exercise_type=ExerciseType.COMPOUND,
        primary_muscle=MuscleGroup.CHEST,
    )
    core_wrapper = SimpleNamespace(
        exercise=SimpleNamespace(
            title="Bench Press",
            exercise_type=ExerciseType.CORE,
            primary_muscle=MuscleGroup.CHEST,
        )
    )
    supplemental_mapping = {
        "exercise": {
            "name": "Barbell Curl",
            "exercise_type": ExerciseType.ISOLATION.value,
            "primary_muscle": MuscleGroup.FOREARMS.value,
        }
    }

    breakdown = exercise_count_breakdown((main, core_wrapper, supplemental_mapping))

    assert breakdown.main_count == 1
    assert breakdown.supplemental_count == 2
    assert breakdown.total_count == 3
    assert main_exercise_count((main, core_wrapper, supplemental_mapping)) == 1


def test_core_duration_is_retained_in_total_session_cost() -> None:
    exercises = (
        SimpleNamespace(exercise_type=ExerciseType.COMPOUND, estimated_minutes=20),
        SimpleNamespace(exercise_type=ExerciseType.CORE, estimated_minutes=8),
    )

    assert calculate_total_session_minutes_from_exercises(exercises, 5) == 33
