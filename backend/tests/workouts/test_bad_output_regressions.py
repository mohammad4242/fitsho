from app.exercises.enums import MovementPattern, MuscleGroup
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal, PhysicalJobDemand, RecoveryRating
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def test_regression_novice_poor_recovery_never_gets_six_demanding_days() -> None:
    source = request(
        available_training_days=6,
        sleep_quality=RecoveryRating.POOR,
        stress_level=RecoveryRating.POOR,
        physical_job_demand=PhysicalJobDemand.HIGH,
    )

    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None, result.errors
    assert len(result.program.weekly_schedule) <= 3


def test_regression_three_day_novice_is_not_push_pull_legs() -> None:
    result = generate_program(request(available_training_days=3), full_catalog(), RULESET)

    assert result.program is not None
    assert all(day.focus.startswith("full_body") for day in result.program.weekly_schedule)


def test_regression_thirty_minute_session_is_not_overfilled() -> None:
    source = request(session_duration_minutes=30)
    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None, result.errors
    assert all(len(day.exercises) <= 3 for day in result.program.weekly_schedule)
    assert all(day.estimated_duration_minutes <= 35 for day in result.program.weekly_schedule)


def test_regression_repeated_exercises_have_progression_reason() -> None:
    result = generate_program(request(available_training_days=3), full_catalog(), RULESET)

    assert result.program is not None
    occurrences: dict[object, list[tuple[str, ...]]] = {}
    for day in result.program.weekly_schedule:
        for item in day.exercises:
            occurrences.setdefault(item.exercise_id, []).append(item.reason_codes)
    assert all(
        all("CORE_MOVEMENT_REPEATED_FOR_PROGRESSION" in reasons for reasons in values[1:])
        for values in occurrences.values()
        if len(values) > 1
    )


def test_regression_fat_loss_is_not_cardio_only() -> None:
    result = generate_program(
        request(primary_goal=Goal.FAT_LOSS), full_catalog(), RULESET
    )

    assert result.program is not None
    assert all(day.exercises for day in result.program.weekly_schedule)
    assert any(day.cardio for day in result.program.weekly_schedule)


def test_regression_strength_is_not_random_high_rep_isolation() -> None:
    result = generate_program(
        request(primary_goal=Goal.STRENGTH), full_catalog(), RULESET
    )

    assert result.program is not None
    first = result.program.weekly_schedule[0].exercises[0]
    assert first.rep_max <= 6
    assert first.movement_pattern in {
        MovementPattern.HORIZONTAL_PUSH,
        MovementPattern.HORIZONTAL_PULL,
        MovementPattern.SQUAT,
        MovementPattern.HIP_HINGE,
    }


def test_regression_priority_muscle_is_early_and_gets_more_planned_volume() -> None:
    source = request(priority_muscles=[MuscleGroup.BACK])
    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None
    assert result.program.weekly_schedule[0].exercises[0].primary_muscle is MuscleGroup.BACK
    planned = result.program.aggregate_metrics["planned_direct_sets_by_muscle"]
    assert planned[MuscleGroup.BACK.value] > planned[MuscleGroup.CHEST.value]
