from types import SimpleNamespace

from app.exercises.enums import ExerciseLabel, ExerciseType
from app.workouts.program_engine.duration_policy import (
    calculate_core_addon_minutes,
    calculate_main_training_minutes,
    calculate_main_training_minutes_from_exercises,
    get_session_duration_policy,
)


def _item(exercise_type: ExerciseType | str, minutes: int, *, cardio: bool = False):
    return SimpleNamespace(
        exercise_type=exercise_type,
        estimated_minutes=minutes,
        labels=frozenset({ExerciseLabel.CARDIO}) if cardio else frozenset(),
    )


def test_main_training_excludes_anatomical_core_and_cardio_only() -> None:
    exercises = (
        _item(ExerciseType.COMPOUND, 35),
        _item(ExerciseType.ISOLATION, 25),
        _item(ExerciseType.CORE, 8),
        _item("cardio", 10, cardio=True),
    )

    assert calculate_main_training_minutes_from_exercises(exercises) == 60
    assert calculate_core_addon_minutes(exercises) == 8


def test_day_main_training_is_independent_of_warmup_core_and_cardio_addons() -> None:
    day = SimpleNamespace(
        exercises=(
            _item(ExerciseType.COMPOUND, 35),
            _item(ExerciseType.ISOLATION, 25),
            _item(ExerciseType.CORE, 8),
        ),
        cardio=SimpleNamespace(duration_minutes=10),
        estimated_duration_minutes=83,
    )

    assert calculate_main_training_minutes(day) == 60
    assert calculate_core_addon_minutes(day.exercises) == 8


def test_duration_policy_contains_main_training_bounds() -> None:
    policy = get_session_duration_policy(60)

    assert (policy.minimum_minutes, policy.maximum_minutes) == (50, 70)
    assert [policy.contains(value) for value in (49, 50, 60, 70, 71)] == [
        False,
        True,
        True,
        True,
        False,
    ]
