from dataclasses import replace

from app.exercises.enums import MuscleGroup
from app.training_templates.tags import TemplateFocusTag
from app.workouts.program_engine import engine
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import SplitType
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import ProgramGenerationRequest, WorkoutProgram
from tests.workouts.program_engine.golden_fixtures import full_catalog, request
from tests.workouts.program_engine.test_template_reference import _upper_lower_reference


def _trace_tokens(program: WorkoutProgram) -> set[str]:
    return {
        reason
        for entry in program.decision_trace
        for reason in (*entry.get("reasons", ()), *entry.get("reason_codes", ()))
    }


def _direct_sets(program: WorkoutProgram, muscle: MuscleGroup) -> int:
    return program.aggregate_metrics["weekly_direct_sets_by_muscle"].get(muscle.value, 0)


def _without_priority(source: ProgramGenerationRequest) -> ProgramGenerationRequest:
    return source.model_copy(update={"priority_muscles": frozenset()})


def test_chest_priority_is_muscle_specific_in_real_generation() -> None:
    source = request(
        available_training_days=4,
        training_experience="advanced",
        training_age_months=72,
        primary_goal="build_muscle",
        session_duration_minutes=30,
        seed_optional=23,
        priority_muscles=[MuscleGroup.CHEST],
    )
    result = generate_program(source, full_catalog(), RULESET)
    baseline = generate_program(_without_priority(source), full_catalog(), RULESET)

    assert result.is_success, result.errors
    assert baseline.is_success, baseline.errors
    assert result.program is not None and baseline.program is not None
    assert result.program.split.split_type is SplitType.UPPER_LOWER_FULL
    assert result.program.weekly_schedule[0].focus == "upper"
    assert _direct_sets(result.program, MuscleGroup.CHEST) >= _direct_sets(
        baseline.program, MuscleGroup.CHEST
    )
    assert set(result.program.aggregate_metrics["priority_metrics"]) == {MuscleGroup.CHEST.value}
    assert not any(
        marker in token.lower()
        for token in _trace_tokens(result.program)
        for marker in ("upper_priority", "upper_specialization")
    )


def test_back_priority_is_muscle_specific_in_real_generation() -> None:
    source = request(
        available_training_days=5,
        training_experience="intermediate",
        training_age_months=24,
        primary_goal="build_muscle",
        session_duration_minutes=30,
        seed_optional=23,
        priority_muscles=[MuscleGroup.BACK],
    )
    result = generate_program(source, full_catalog(), RULESET)

    assert result.is_success, result.errors
    assert result.program is not None
    assert any(day.focus == "pull" for day in result.program.weekly_schedule)
    assert set(result.program.aggregate_metrics["priority_metrics"]) == {MuscleGroup.BACK.value}
    assert (
        result.program.aggregate_metrics["priority_metrics"][MuscleGroup.BACK.value]["direct_sets"]
        > 0
    )
    assert not any(
        marker in token.lower()
        for token in _trace_tokens(result.program)
        for marker in ("upper_priority", "upper_specialization")
    )


def test_biceps_priority_selects_the_best_canonical_quality_after_fallback() -> None:
    source = request(
        available_training_days=6,
        training_experience="advanced",
        training_age_months=72,
        primary_goal="build_muscle",
        session_duration_minutes=60,
        seed_optional=23,
        priority_muscles=[MuscleGroup.BICEPS],
    )
    result = generate_program(source, full_catalog(), RULESET)

    assert result.is_success, result.errors
    assert result.program is not None
    assert result.program.split.split_type is SplitType.UPPER_LOWER_X3
    assert result.program.weekly_schedule[-1].focus == "lower"
    assert "SPLIT_FALLBACK_AFTER_CONSTRUCTION_FAILURE" in result.program.split.reason_codes
    recovery = next(
        entry
        for entry in result.program.decision_trace
        if entry["stage"] == "construction_recovery"
    )
    assert recovery["selected_split"] == SplitType.UPPER_LOWER_X3.value
    assert recovery["rejected_splits"] == ()
    assert set(result.program.aggregate_metrics["priority_metrics"]) == {MuscleGroup.BICEPS.value}
    assert (
        result.program.aggregate_metrics["priority_metrics"][MuscleGroup.BICEPS.value][
            "direct_sets"
        ]
        > 0
    )
    assert not any(
        marker in token.lower()
        for token in _trace_tokens(result.program)
        for marker in ("upper_priority", "upper_specialization")
    )


def test_no_priority_user_can_still_use_a_structural_upper_lower_template(monkeypatch) -> None:
    reference, catalog = _upper_lower_reference()
    reference = replace(reference, focus_tags=(TemplateFocusTag.UPPER_LOWER.value,))
    monkeypatch.setattr(engine, "rank_split_candidates", lambda *args, **kwargs: ())
    result = generate_program(
        request(
            available_training_days=4,
            primary_goal="build_muscle",
            training_experience="intermediate",
            training_age_months=24,
            session_duration_minutes=30,
            seed_optional=23,
        ),
        catalog,
        RULESET,
        reference_templates=(reference,),
    )

    assert result.is_success, result.errors
    assert result.program is not None
    assert result.program.aggregate_metrics["reference_template"] == reference.slug
    assert result.program.split.split_type is SplitType.UPPER_LOWER
    assert result.program.split.day_focuses == ("upper", "lower", "upper", "lower")
    assert result.program.aggregate_metrics["priority_metrics"] == {}


def test_lower_priority_keeps_lower_behavior_without_upper_priority_leakage() -> None:
    source = request(
        available_training_days=4,
        training_experience="intermediate",
        training_age_months=24,
        primary_goal="build_muscle",
        session_duration_minutes=30,
        seed_optional=23,
        priority_muscles=[MuscleGroup.GLUTES],
    )
    result = generate_program(source, full_catalog(), RULESET)
    baseline = generate_program(_without_priority(source), full_catalog(), RULESET)

    assert result.is_success, result.errors
    assert baseline.is_success, baseline.errors
    assert result.program is not None and baseline.program is not None
    assert _direct_sets(result.program, MuscleGroup.GLUTES) > _direct_sets(
        baseline.program, MuscleGroup.GLUTES
    )
    assert set(result.program.aggregate_metrics["priority_metrics"]) == {MuscleGroup.GLUTES.value}
    assert not any("upper_priority" in token.lower() for token in _trace_tokens(result.program))
