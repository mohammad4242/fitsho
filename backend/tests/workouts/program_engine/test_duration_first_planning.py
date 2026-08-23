from uuid import uuid4

import pytest

from app.exercises.enums import Equipment, ExerciseCautionTag, MuscleGroup
from app.workouts.program_engine.duration_policy import get_session_duration_policy
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import BodyAnalysisInfluence, WorkoutProgram
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def _source(goal: Goal, duration: int, **overrides: object):
    values: dict[str, object] = {
        "primary_goal": goal,
        "session_duration_minutes": duration,
        "available_training_days": 3,
        "training_experience": "intermediate",
        "training_age_months": 30,
    }
    values.update(overrides)
    return request(**values)


def _program(goal: Goal, duration: int, **overrides: object) -> WorkoutProgram:
    source = _source(goal, duration, **overrides)
    result = generate_program(source, full_catalog(), RULESET, reference_templates=())
    assert result.program is not None, result.errors
    return result.program


def _body_lag(muscle: MuscleGroup) -> BodyAnalysisInfluence:
    return BodyAnalysisInfluence.model_validate(
        {
            "analysis_id": uuid4(),
            "result_version_id": uuid4(),
            "analysis_revision": 1,
            "schema_version": "1.0",
            "source": "fully_reviewed",
            "overall_confidence": 0.9,
            "priorities": [
                {
                    "muscle": muscle,
                    "classification": "clear_lag",
                    "confidence": 0.9,
                    "severity": 0.8,
                    "emphasis": [muscle.value],
                }
            ],
        }
    )


@pytest.mark.parametrize(
    ("goal", "duration"),
    (
        (Goal.HYPERTROPHY, 30),
        (Goal.HYPERTROPHY, 45),
        (Goal.HYPERTROPHY, 60),
        (Goal.HYPERTROPHY, 90),
        (Goal.MUSCULAR_ENDURANCE, 45),
    ),
)
def test_final_program_duration_matrix_is_valid(goal: Goal, duration: int) -> None:
    program = _program(goal, duration)
    policy = get_session_duration_policy(duration)

    assert program.validation_report.is_valid
    assert len(program.weekly_schedule) == 3
    resistance_time_budget_fit = all(
        day.estimated_duration_minutes - RULESET.general_warmup_minutes <= policy.maximum_minutes
        for day in program.weekly_schedule
    )
    assert (
        resistance_time_budget_fit
        or "SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD" in program.warnings
    )
    assert all(
        item.sets <= RULESET.max_working_sets_per_exercise_absolute
        for day in program.weekly_schedule
        for item in day.exercises
    )


def test_fat_loss_reserves_cardio_before_resistance_construction() -> None:
    source = _source(Goal.FAT_LOSS, 30)
    result = generate_program(source, full_catalog(), RULESET, reference_templates=())

    assert result.program is not None, result.errors
    capacity = next(
        entry for entry in result.program.decision_trace if entry["stage"] == "duration_capacity"
    )
    # Phase 11.9: Cardio no longer reduces the resistance budget.
    assert capacity["resistance_work_budget_minutes"] == source.session_duration_minutes
    assert any(day.cardio is not None for day in result.program.weekly_schedule)


def test_same_profile_gets_more_useful_capacity_at_sixty_minutes() -> None:
    short = _program(Goal.HYPERTROPHY, 30)
    long = _program(Goal.HYPERTROPHY, 60)

    short_work = sum(item.sets for day in short.weekly_schedule for item in day.exercises)
    long_work = sum(item.sets for day in long.weekly_schedule for item in day.exercises)
    short_capacity = next(
        entry for entry in short.decision_trace if entry["stage"] == "duration_capacity"
    )
    long_capacity = next(
        entry for entry in long.decision_trace if entry["stage"] == "duration_capacity"
    )
    assert (
        long_capacity["expected_exercise_count_capacity"]
        > short_capacity["expected_exercise_count_capacity"]
    )
    assert (
        long_capacity["expected_working_set_capacity"]
        > short_capacity["expected_working_set_capacity"]
    )
    assert long_work > short_work


def test_short_session_preserves_explicit_priority_above_body_analysis() -> None:
    program = _program(
        Goal.HYPERTROPHY,
        30,
        priority_muscles=[MuscleGroup.CHEST],
        body_analysis_influence=_body_lag(MuscleGroup.GLUTES),
    )
    ranges = program.aggregate_metrics["volume_ranges_by_muscle"]

    assert ranges["chest"]["preferred_weekly_target"] > ranges["glutes"]["preferred_weekly_target"]
    assert (
        ranges["chest"]["minimum_direct_sets"]
        >= RULESET.minimum_coverage_sets[program.training_status]
    )
    assert program.aggregate_metrics["priority_metrics"]["chest"]["status"] in {
        "satisfied",
        "partial",
    }
    assert ranges["chest"]["actual_direct_volume"] > ranges["glutes"]["actual_direct_volume"]


def test_final_split_is_duration_planned_and_keeps_exact_days() -> None:
    source = _source(Goal.STRENGTH, 30, available_training_days=4)
    result = generate_program(source, full_catalog(), RULESET, reference_templates=())

    assert result.program is not None, result.errors
    assert len(result.program.weekly_schedule) == source.available_training_days
    assert result.program.aggregate_metrics.get("reference_template") is None
    assert any(
        reason.startswith("SPLIT_DURATION_CAPACITY_")
        for reason in result.program.split.reason_codes
    )


def test_duration_planning_never_relaxes_safety_or_equipment() -> None:
    source = _source(
        Goal.HYPERTROPHY,
        30,
        available_equipment=[Equipment.BODYWEIGHT],
        blocked_caution_tags=[ExerciseCautionTag.DEEP_KNEE_FLEXION],
    )
    result = generate_program(source, full_catalog(), RULESET, reference_templates=())

    assert result.program is not None, result.errors
    exercises = tuple(item for day in result.program.weekly_schedule for item in day.exercises)
    assert all(item.equipment.issubset({Equipment.BODYWEIGHT}) for item in exercises)
    assert all(ExerciseCautionTag.DEEP_KNEE_FLEXION not in item.caution_tags for item in exercises)


def test_reversed_candidate_order_keeps_final_duration_plan_deterministic() -> None:
    source = _source(Goal.HYPERTROPHY, 45, available_training_days=4)
    catalog = full_catalog()

    first = generate_program(source, catalog, RULESET, reference_templates=())
    second = generate_program(source, list(reversed(catalog)), RULESET, reference_templates=())

    assert first.program is not None, first.errors
    assert second.program is not None, second.errors
    assert first.program == second.program


def test_long_session_does_not_exceed_useful_or_hard_volume_to_fill_time() -> None:
    program = _program(Goal.HYPERTROPHY, 90)
    ranges = program.aggregate_metrics["volume_ranges_by_muscle"]

    assert all(
        values["actual_effective_volume"] <= values["effective_maximum_hard"]
        for values in ranges.values()
    )
    assert all(
        len(day.exercises) <= RULESET.max_exercises_per_session for day in program.weekly_schedule
    )
