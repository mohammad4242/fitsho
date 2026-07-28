from app.workouts.time_budget import (
    ExerciseTiming,
    WorkoutGenerationPolicy,
    calculate_day_minutes,
    fits_session_duration,
)


def test_duration_calculation_includes_sets_rest_and_transition_time() -> None:
    estimated = calculate_day_minutes([ExerciseTiming(sets=3, rest_seconds=90)])

    assert estimated == 8


def test_duration_rejects_session_overflow() -> None:
    policy = WorkoutGenerationPolicy.for_session_duration(30)
    exercises = [ExerciseTiming(sets=5, rest_seconds=180)] * 2

    assert calculate_day_minutes(exercises) > 20
    assert not fits_session_duration(exercises, policy)
