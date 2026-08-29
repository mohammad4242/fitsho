from dataclasses import asdict

from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import ValidationStatus
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import ValidationReport
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


def _report(*, errors: tuple[str, ...] = (), warnings: tuple[str, ...] = ()) -> ValidationReport:
    return ValidationReport(
        errors=errors,
        warnings=warnings,
        assumptions=(),
        metrics={},
        decision_trace=(),
    )


def test_validation_outcomes_preserve_is_valid_compatibility() -> None:
    valid = _report()
    constrained = _report(warnings=("SOFT_TARGET_CONSTRAINED",))
    invalid = _report(errors=("HARD_REQUIREMENT_FAILED",))

    assert valid.status is ValidationStatus.VALID
    assert valid.is_valid is True
    assert constrained.status is ValidationStatus.VALID_WITH_CONSTRAINTS
    assert constrained.is_valid is True
    assert asdict(constrained)["status"] is ValidationStatus.VALID_WITH_CONSTRAINTS
    assert invalid.status is ValidationStatus.INVALID
    assert invalid.is_valid is False


def test_safe_priority_soft_shortfall_remains_a_usable_program() -> None:
    result = generate_program(
        request(
            available_training_days=1,
            session_duration_minutes=45,
            priority_muscles=[MuscleGroup.CHEST],
        ),
        full_catalog(),
        RULESET,
    )

    assert result.program is not None, result.errors
    assert result.program.validation_report.status is ValidationStatus.VALID_WITH_CONSTRAINTS
    assert "DIRECT_VOLUME_BELOW_SOFT_TARGET" in result.program.validation_report.warnings


def test_coach_quality_metrics_are_deterministic_and_decomposed() -> None:
    source = request(
        available_training_days=1,
        session_duration_minutes=45,
        priority_muscles=[MuscleGroup.CHEST],
    )

    first = generate_program(source, full_catalog(), RULESET)
    second = generate_program(source, full_catalog(), RULESET)

    assert first.program is not None, first.errors
    assert second.program is not None, second.errors
    first_quality = next(
        item["metrics"]
        for item in first.program.decision_trace
        if item.get("stage") == "coach_quality"
    )
    second_quality = next(
        item["metrics"]
        for item in second.program.decision_trace
        if item.get("stage") == "coach_quality"
    )
    assert first_quality == second_quality
    assert set(first_quality) == {
        "template_preservation",
        "priority_target_satisfaction",
        "body_analysis_target_satisfaction",
        "volume_fit",
        "duration_fit",
        "coverage_fit",
        "recovery_fit",
        "substitution_count",
        "constraint_count",
        "hard_validation_status",
    }
    assert "overall_quality_score" not in first_quality
    assert first_quality["hard_validation_status"] == "VALID_WITH_CONSTRAINTS"
