from dataclasses import asdict

from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.coach_quality import (
    _coverage_quality,
    _priority_quality_floor,
    _volume_fit,
)
from app.workouts.program_engine.engine import _volume_range_metric, generate_program
from app.workouts.program_engine.enums import ValidationStatus
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import ValidationReport, VolumeTarget
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
        "schema_version",
        "selection_quality",
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


def test_volume_quality_uses_validation_aligned_constraint_volume() -> None:
    metrics = {
        "volume_ranges_by_muscle": {
            "chest": {
                "actual_direct_volume": 2,
                "actual_effective_volume": 10,
                "actual_constraint_volume": 2,
                "acceptable_minimum": 5,
                "acceptable_maximum": 20,
            }
        }
    }

    assert _volume_fit(metrics) == {"satisfied": 0.0, "total": 1.0, "percentage": 0.0}


def test_priority_quality_uses_only_applicable_dimensions() -> None:
    metrics = {
        "chest": {
            "direct_sets": 2,
            "target_sets": 4,
            "effective_sets": 6,
            "effective_target_sets": 8,
            "session_frequency": 1,
            "preferred_frequency": 2,
        },
        "back": {
            "direct_sets": 0,
            "target_sets": 0,
            "effective_sets": 2,
            "effective_target_sets": 4,
            "session_frequency": 2,
            "preferred_frequency": 2,
        },
        "calves": {
            "direct_sets": 0,
            "target_sets": 0,
            "effective_sets": 2,
            "effective_target_sets": 0,
            "session_frequency": 0,
            "preferred_frequency": 0,
        },
    }

    assert _priority_quality_floor(metrics, frozenset({"chest"})) == 50.0
    assert _priority_quality_floor(metrics, frozenset({"back"})) == 50.0
    assert _priority_quality_floor(metrics, frozenset({"calves"})) is None


def test_non_full_body_coverage_quality_uses_volume_evidence() -> None:
    quality = _coverage_quality(
        {
            "weekly_coverage": {"status": "not_applicable"},
            "volume_ranges_by_muscle": {
                "chest": {
                    "actual_constraint_volume": 6,
                    "acceptable_minimum": 6,
                    "minimum_coverage_required": True,
                },
                "back": {
                    "actual_constraint_volume": 2,
                    "acceptable_minimum": 6,
                    "minimum_coverage_required": True,
                },
                "biceps": {
                    "actual_constraint_volume": 0,
                    "acceptable_minimum": 4,
                    "minimum_coverage_required": False,
                },
            },
        }
    )

    assert quality == {"coverage_state": "proven_constrained", "coverage_percentage": 50.0}


def test_volume_evidence_exposes_the_constraint_aligned_value() -> None:
    target = VolumeTarget(
        muscle=MuscleGroup.CHEST,
        minimum_soft=6,
        target_sets=8,
        maximum_soft=12,
        maximum_hard=14,
        fractional_sets=8.0,
        effective_target_sets=8,
        minimum_direct_sets=6,
    )

    evidence = _volume_range_metric(target, 2, 10.0, (), (), 24)

    assert evidence["actual_constraint_volume"] == 2
