from app.exercises.enums import ExerciseType, MovementPattern, MuscleGroup
from app.workouts.program_engine.duration_policy import get_session_duration_policy
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import (
    Goal,
    PhysicalJobDemand,
    RecoveryRating,
    TrainingExperience,
)
from app.workouts.program_engine.recovery import recovery_spacing_is_valid
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import RecentTrainingHistory
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def test_regression_novice_poor_recovery_keeps_exact_days_with_valid_spacing() -> None:
    source = request(
        available_training_days=6,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=24,
        sleep_quality=RecoveryRating.POOR,
        stress_level=RecoveryRating.POOR,
        physical_job_demand=PhysicalJobDemand.HIGH,
    )

    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None, result.errors
    assert len(result.program.weekly_schedule) == 6
    assert recovery_spacing_is_valid(result.program.weekly_schedule, RULESET)


def test_regression_three_day_novice_is_not_push_pull_legs() -> None:
    result = generate_program(request(available_training_days=3), full_catalog(), RULESET)

    assert result.program is not None
    assert all(day.focus.startswith("full_body") for day in result.program.weekly_schedule)


def test_regression_thirty_minute_session_reports_traceable_constrained_workload() -> None:
    source = request(session_duration_minutes=30)
    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None, result.errors
    assert all(
        2 <= len(day.exercises) <= RULESET.max_exercises_per_session
        for day in result.program.weekly_schedule
    )
    assert all(
        item.counts_toward_volume
        for day in result.program.weekly_schedule
        for item in day.exercises
    )
    assert result.program.validation_report.is_valid
    volume_repair = next(
        entry for entry in result.program.decision_trace if entry["stage"] == "volume_repair"
    )
    assert "VOLUME_REPAIR_SOFT_TARGET_REDUCED" in volume_repair["reasons"]
    assert "PLANNED_SOFT_VOLUME_REDUCED_DURING_SESSION_FIT" in result.program.warnings
    policy = get_session_duration_policy(source.session_duration_minutes)
    assert all(
        policy.contains_total(day.estimated_duration_minutes, RULESET.general_warmup_minutes)
        for day in result.program.weekly_schedule
    )


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
    result = generate_program(request(primary_goal=Goal.FAT_LOSS), full_catalog(), RULESET)

    assert result.program is not None
    assert all(day.exercises for day in result.program.weekly_schedule)
    assert any(day.cardio for day in result.program.weekly_schedule)


def test_regression_strength_is_not_random_high_rep_isolation() -> None:
    result = generate_program(request(primary_goal=Goal.STRENGTH), full_catalog(), RULESET)

    assert result.program is not None
    first = result.program.weekly_schedule[0].exercises[0]
    assert first.exercise_type is ExerciseType.COMPOUND
    assert "STRENGTH_PRIMARY_COMPOUND" in first.reason_codes
    assert first.rep_max <= RULESET.strength_beginner_rep_maximums["primary_strength"]
    assert first.movement_pattern in {
        MovementPattern.HORIZONTAL_PUSH,
        MovementPattern.HORIZONTAL_PULL,
        MovementPattern.VERTICAL_PUSH,
        MovementPattern.VERTICAL_PULL,
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


def test_regression_short_sessions_cover_hinge_and_core_across_the_week() -> None:
    result = generate_program(
        request(available_training_days=3, session_duration_minutes=25),
        full_catalog(),
        RULESET,
    )

    assert result.program is not None, result.errors
    patterns = {
        item.movement_pattern for day in result.program.weekly_schedule for item in day.exercises
    }
    assert MovementPattern.HIP_HINGE in patterns
    assert MovementPattern.CORE_ANTI_EXTENSION in patterns

def test_regression_short_upper_lower_keeps_required_trunk_work_with_cardio() -> None:
    result = generate_program(
        request(
            available_training_days=4,
            session_duration_minutes=25,
            primary_goal=Goal.HYPERTROPHY,
            training_experience=TrainingExperience.INTERMEDIATE,
            training_age_months=30,
            recent_training_history=RecentTrainingHistory(consistent_weeks=20),
        ),
        full_catalog(),
        RULESET,
    )

    assert result.program is not None, result.errors
    assert any(
        item.movement_pattern is MovementPattern.CORE_ANTI_EXTENSION
        for day in result.program.weekly_schedule
        for item in day.exercises
    )
    assert any(day.cardio is not None for day in result.program.weekly_schedule)
    assert all(
        day.cardio is None or "CARDIO_SCHEDULED_AFTER_RESISTANCE" in day.cardio.reason_codes
        for day in result.program.weekly_schedule
    )
    assert all(
        day.estimated_duration_minutes
        <= get_session_duration_policy(25).maximum_total_minutes(RULESET.general_warmup_minutes)
        for day in result.program.weekly_schedule
    )
