from app.exercises.enums import Equipment, MuscleGroup
from app.profile.enums import TrainingLocation
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal, SplitType, TrainingExperience
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import ProgramGenerationRequest
from app.workouts.program_engine.split_selector import rank_split_candidates

from .golden_fixtures import ADVANCED_HISTORY, full_catalog, request


def _six_day_priority_request(*, priorities: frozenset[MuscleGroup]) -> ProgramGenerationRequest:
    return request(
        primary_goal=Goal.MUSCLE_GAIN,
        training_experience=TrainingExperience.ADVANCED,
        training_age_months=72,
        available_training_days=6,
        session_duration_minutes=45,
        available_equipment=frozenset(
            {
                Equipment.BODYWEIGHT,
                Equipment.DUMBBELL,
                Equipment.BARBELL,
                Equipment.BENCH,
                Equipment.CABLE,
                Equipment.MACHINE,
            }
        ),
        training_location=TrainingLocation.GYM,
        priority_muscles=priorities,
        recent_training_history=ADVANCED_HISTORY,
    )


def test_six_day_priority_prefers_a_split_with_twice_weekly_priority_exposure() -> None:
    source = _six_day_priority_request(
        priorities=frozenset({MuscleGroup.HAMSTRINGS, MuscleGroup.QUADRICEPS})
    )
    normalized = normalize_request(source, RULESET)

    ranked = rank_split_candidates(normalized, RULESET)

    assert ranked[0].split_type is SplitType.PUSH_PULL_LEGS_X2
    assert "PRIORITY_FREQUENCY_INCREASED" in ranked[0].reason_codes


def test_priority_program_reports_measurable_emphasis_and_frequency_for_each_priority() -> None:
    baseline = generate_program(
        _six_day_priority_request(priorities=frozenset()), full_catalog(), RULESET
    )
    priority = generate_program(
        _six_day_priority_request(
            priorities=frozenset({MuscleGroup.HAMSTRINGS, MuscleGroup.QUADRICEPS})
        ),
        full_catalog(),
        RULESET,
    )

    assert baseline.program is not None, baseline.errors
    assert priority.program is not None, priority.errors
    assert len(priority.program.weekly_schedule) == 6
    assert all(
        35 <= day.estimated_duration_minutes <= 55
        for day in priority.program.weekly_schedule
    )
    assert all(
        item.sets <= RULESET.max_working_sets_per_exercise_absolute
        for day in priority.program.weekly_schedule
        for item in day.exercises
    )
    volume_trace = next(
        entry for entry in priority.program.decision_trace if entry["stage"] == "volume"
    )
    assert volume_trace["priority_preferred_frequency"] == 2
    assert set(volume_trace["priority_muscles"]) == {
        MuscleGroup.HAMSTRINGS.value,
        MuscleGroup.QUADRICEPS.value,
    }
    priority_metrics = priority.program.aggregate_metrics["priority_metrics"]
    baseline_direct = baseline.program.aggregate_metrics["weekly_direct_sets_by_muscle"]

    for muscle in (MuscleGroup.HAMSTRINGS, MuscleGroup.QUADRICEPS):
        metrics = priority_metrics[muscle.value]
        assert metrics["direct_sets"] > baseline_direct[muscle.value]
        assert metrics["effective_sets"] >= metrics["direct_sets"]
        assert metrics["session_frequency"] >= 2
        assert len(metrics["session_indexes"]) == metrics["session_frequency"]
        weekdays = [
            priority.program.weekly_schedule[index - 1].weekday
            for index in metrics["session_indexes"]
        ]
        assert all(
            current is not None
            and following is not None
            and following - current >= RULESET.minimum_recovery_gap_days
            for current, following in zip(weekdays, weekdays[1:], strict=False)
        )


def test_multiple_priority_muscles_receive_deterministic_balanced_emphasis() -> None:
    source = _six_day_priority_request(
        priorities=frozenset(
            {MuscleGroup.BICEPS, MuscleGroup.SHOULDERS, MuscleGroup.TRICEPS}
        )
    )

    first = generate_program(source, full_catalog(), RULESET)
    second = generate_program(source, list(reversed(full_catalog())), RULESET)

    assert first.program is not None, first.errors
    assert second.program is not None, second.errors
    first_metrics = first.program.aggregate_metrics["priority_metrics"]
    second_metrics = second.program.aggregate_metrics["priority_metrics"]
    first_values = {
        muscle.value: (
            first_metrics[muscle.value]["direct_sets"],
            first_metrics[muscle.value]["session_frequency"],
        )
        for muscle in (MuscleGroup.BICEPS, MuscleGroup.SHOULDERS, MuscleGroup.TRICEPS)
    }
    second_values = {
        muscle.value: (
            second_metrics[muscle.value]["direct_sets"],
            second_metrics[muscle.value]["session_frequency"],
        )
        for muscle in (MuscleGroup.BICEPS, MuscleGroup.SHOULDERS, MuscleGroup.TRICEPS)
    }

    assert first_values == second_values
    for muscle in (MuscleGroup.BICEPS, MuscleGroup.SHOULDERS, MuscleGroup.TRICEPS):
        assert first_metrics[muscle.value]["session_frequency"] >= 2
        assert first_metrics[muscle.value]["distributed"] is True
        volume_range = first.program.aggregate_metrics["volume_ranges_by_muscle"][muscle.value]
        assert (
            first_metrics[muscle.value]["effective_sets"]
            >= volume_range["acceptable_minimum"]
        )
        assert volume_range["status"] in {"exact_target", "within_flexible_range"}


def test_priority_warning_is_explicit_when_catalog_cannot_provide_frequency_capacity() -> None:
    result = generate_program(
        request(
            primary_goal=Goal.MUSCLE_GAIN,
            training_experience=TrainingExperience.INTERMEDIATE,
            training_age_months=30,
            available_training_days=4,
            session_duration_minutes=45,
            priority_muscles=[MuscleGroup.GLUTES],
        ),
        full_catalog(),
        RULESET,
    )

    assert result.program is not None, result.errors
    metrics = result.program.aggregate_metrics["priority_metrics"][MuscleGroup.GLUTES.value]
    assert metrics["status"] == "partial"
    assert metrics["session_frequency"] < metrics["preferred_frequency"]
    assert "PRIORITY_TARGET_CONSTRAINED" in metrics["reason_codes"]
    assert "PRIORITY_TARGET_PARTIALLY_SATISFIED" in result.program.warnings


def test_priority_does_not_override_existing_hard_constraints() -> None:
    source = _six_day_priority_request(
        priorities=frozenset({MuscleGroup.HAMSTRINGS, MuscleGroup.QUADRICEPS})
    ).model_copy(update={"available_training_days": 4})
    result = generate_program(
        source,
        [item for item in full_catalog() if Equipment.DUMBBELL not in item.equipment],
        RULESET,
    )

    assert result.program is not None, result.errors
    assert len(result.program.weekly_schedule) == source.available_training_days
    assert all(
        item.equipment.issubset(source.available_equipment)
        for day in result.program.weekly_schedule
        for item in day.exercises
    )
    assert all(
        item.sets
        <= RULESET.max_working_sets_for_exercise(
            training_status=result.program.training_status,
            goal=source.primary_goal,
            exercise_type=item.exercise_type,
            is_priority=item.primary_muscle in source.priority_muscles,
            weekly_exposure_count=sum(
                any(
                    selected.primary_muscle is item.primary_muscle
                    for selected in day.exercises
                )
                for day in result.program.weekly_schedule
            ),
        )
        for day in result.program.weekly_schedule
        for item in day.exercises
    )
