from app.exercises.enums import Equipment, MuscleGroup
from app.profile.enums import TrainingLocation
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal, SplitType, TrainingExperience
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.priority_allocation import PriorityAllocationPolicy
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import BodyAnalysisInfluence, ProgramGenerationRequest
from app.workouts.program_engine.split_selector import rank_split_candidates, select_split
from app.workouts.program_engine.volume_planner import plan_weekly_volume

from .golden_fixtures import ADVANCED_HISTORY, full_catalog, request


def _body_lags(*items: tuple[MuscleGroup, str]) -> BodyAnalysisInfluence:
    return BodyAnalysisInfluence.model_validate(
        {
            "analysis_id": "10000000-0000-0000-0000-000000000001",
            "result_version_id": "10000000-0000-0000-0000-000000000002",
            "analysis_revision": 1,
            "schema_version": "1.0",
            "source": "coach_reviewed",
            "overall_confidence": 0.95,
            "priorities": [
                {
                    "muscle": muscle,
                    "classification": classification,
                    "confidence": 0.9,
                    "severity": 0.8 if classification == "clear_lag" else 0.4,
                    "emphasis": [muscle.value],
                }
                for muscle, classification in items
            ],
        }
    )


def _planned_targets(priorities: frozenset[MuscleGroup]) -> dict[MuscleGroup, int]:
    source = request(priority_muscles=priorities)
    normalized = normalize_request(source, RULESET)
    plan = plan_weekly_volume(normalized, select_split(normalized, RULESET), RULESET)
    return {target.muscle: target.target_sets for target in plan.targets}


def test_priority_precedence_is_explicit_then_clear_then_mild() -> None:
    source = request(
        priority_muscles=[MuscleGroup.CHEST],
        body_analysis_influence=_body_lags(
            (MuscleGroup.BACK, "clear_lag"),
            (MuscleGroup.SHOULDERS, "mild_lag"),
        ),
    )
    policy = PriorityAllocationPolicy.for_request(normalize_request(source, RULESET), RULESET)

    assert policy.precedence_key(MuscleGroup.CHEST)[0] == 0
    assert policy.precedence_key(MuscleGroup.BACK)[0] == 1
    assert policy.precedence_key(MuscleGroup.SHOULDERS)[0] == 2


def test_same_muscle_priority_and_body_analysis_do_not_double_stack() -> None:
    explicit = request(priority_muscles=[MuscleGroup.CHEST])
    supported = explicit.model_copy(
        update={"body_analysis_influence": _body_lags((MuscleGroup.CHEST, "clear_lag"))}
    )
    explicit_normalized = normalize_request(explicit, RULESET)
    supported_normalized = normalize_request(supported, RULESET)

    explicit_plan = plan_weekly_volume(
        explicit_normalized,
        select_split(explicit_normalized, RULESET),
        RULESET,
    )
    supported_plan = plan_weekly_volume(
        supported_normalized,
        select_split(supported_normalized, RULESET),
        RULESET,
    )

    assert supported_plan.direct_sets_for(MuscleGroup.CHEST) == explicit_plan.direct_sets_for(
        MuscleGroup.CHEST
    )
    assert "BODY_ANALYSIS_SUPPORTS_EXPLICIT_PRIORITY" in supported_plan.reason_codes


def test_multiple_priorities_share_the_capped_emphasis_budget() -> None:
    baseline = _planned_targets(frozenset())
    requested = (
        frozenset({MuscleGroup.CHEST}),
        frozenset({MuscleGroup.CHEST, MuscleGroup.BACK}),
        frozenset({MuscleGroup.CHEST, MuscleGroup.BACK, MuscleGroup.SHOULDERS}),
        frozenset(
            {
                MuscleGroup.CHEST,
                MuscleGroup.BACK,
                MuscleGroup.SHOULDERS,
                MuscleGroup.BICEPS,
                MuscleGroup.TRICEPS,
            }
        ),
    )
    expected_budgets = (2, 2, 3, 4)

    for priorities, expected_budget in zip(requested, expected_budgets, strict=True):
        targets = _planned_targets(priorities)
        allocated = sum(targets[muscle] - baseline[muscle] for muscle in priorities)
        assert allocated == expected_budget


def test_priority_frequency_is_only_increased_when_volume_needs_distribution() -> None:
    normalized = normalize_request(
        request(
            available_training_days=6,
            primary_goal=Goal.MUSCLE_GAIN,
            training_experience=TrainingExperience.ADVANCED,
            training_age_months=72,
            priority_muscles=[MuscleGroup.CHEST],
            recent_training_history=ADVANCED_HISTORY,
        ),
        RULESET,
    )
    policy = PriorityAllocationPolicy.for_request(normalized, RULESET)

    assert policy.useful_frequency(5, RULESET) == 1
    assert policy.useful_frequency(9, RULESET) == 2


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
    workout_durations = tuple(
        day.estimated_duration_minutes - RULESET.general_warmup_minutes
        for day in priority.program.weekly_schedule
    )
    assert all(duration <= 55 for duration in workout_durations)
    if any(duration < 35 for duration in workout_durations):
        assert "SESSION_DURATION_CONSTRAINED_BY_HARD_VOLUME_LIMITS" in (
            priority.program.validation_report.warnings
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
        priorities=frozenset({MuscleGroup.BICEPS, MuscleGroup.SHOULDERS, MuscleGroup.TRICEPS})
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
        assert first_metrics[muscle.value]["effective_sets"] >= volume_range["acceptable_minimum"]
        assert volume_range["status"] in {
            "exact_target",
            "within_flexible_range",
            "constrained",
        }
        if volume_range["status"] == "constrained":
            assert volume_range["actual_effective_volume"] <= volume_range["effective_maximum_hard"]
        assert (
            first_metrics[muscle.value]["effective_sets"] <= volume_range["effective_maximum_hard"]
        )


def test_priority_is_satisfied_when_catalog_can_provide_frequency_capacity() -> None:
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
    assert metrics["status"] == "satisfied"
    assert metrics["session_frequency"] >= metrics["preferred_frequency"]
    assert "PRIORITY_FREQUENCY_INCREASED" in metrics["reason_codes"]


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
                any(selected.primary_muscle is item.primary_muscle for selected in day.exercises)
                for day in result.program.weekly_schedule
            ),
        )
        for day in result.program.weekly_schedule
        for item in day.exercises
    )
