from collections import Counter
from copy import deepcopy
from dataclasses import asdict
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

import tests.workouts.program_engine.phase11_benchmark as benchmark
from analyze_stage4 import render_report
from app.exercises.enums import MuscleGroup
from app.exercises.service import seed_exercises
from app.profile.enums import TrainingCaution
from app.training_templates.models import TrainingProgramTemplate
from app.workouts.program_engine.duration_policy import OFFICIAL_SESSION_DURATIONS
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import ProgramGenerationResult
from tests.workouts.program_engine.golden_fixtures import full_catalog
from tests.workouts.program_engine.phase11_benchmark import (
    NEGATIVE_PROFILES,
    SUPPORTED_MATRIX,
    benchmark_profiles,
    canonical_fingerprint,
    profile_to_request,
)


def _successful_result(*, warnings: tuple[str, ...] = ()) -> SimpleNamespace:
    return SimpleNamespace(
        program=SimpleNamespace(
            validation_report=SimpleNamespace(warnings=warnings),
        )
    )


def _valid_closeout_payload() -> dict[str, object]:
    profiles = [
        {
            "input": benchmark._jsonable(asdict(profile)),
            "category": "PASS",
            "audit_findings": [],
            "determinism": {"identical": True},
            "semantic_substitution": {"unexplained_final_semantic_failures": 0},
            "template": {"recovered_with_alternative": False},
        }
        for profile in benchmark_profiles()
    ]
    return {
        "catalog": {
            "exercise_count": 407,
            "template_count": benchmark.EXPECTED_TEMPLATE_COUNT,
            "template_slugs": list(benchmark.EXPECTED_TEMPLATE_SLUGS),
            "catalog_hash": "a" * 64,
            "template_hash": "b" * 64,
            "template_seed_hash": benchmark.EXPECTED_TEMPLATE_SEED_HASH,
        },
        "supported_matrix": list(SUPPORTED_MATRIX),
        "aggregate": {
            "profiles_tested": benchmark.EXPECTED_PROFILE_COUNT,
            "category_counts": {
                "PASS": benchmark.EXPECTED_PROFILE_COUNT,
                "PASS_WITH_CONSTRAINTS": 0,
                "QUALITY_ISSUE": 0,
                "UNSATISFIED": 0,
                "ENGINE_BUG": 0,
            },
            "equipment_violations": 0,
            "safety_violations": 0,
            "redundancy_findings": 0,
            "fallback": {"unsat_classifications": {}, "unsatisfied_generations": 0},
            "quality": {
                "determinism_runs": benchmark.EXPECTED_PROFILE_COUNT,
                "determinism_identical": benchmark.EXPECTED_PROFILE_COUNT,
                "equipment_violations_custom": 0,
                "safety_violations_custom": 0,
                "redundancy_violations_custom": 0,
                "quality_code_audit": {},
                "semantic_substitution": {
                    "unexplained_final_semantic_failures": 0,
                },
            },
        },
        "determinism": {
            "cases": benchmark.EXPECTED_PROFILE_COUNT,
            "rate": 1.0,
            "mismatches": [],
        },
        "negative_cases": [{"rejected_correctly": True} for _ in NEGATIVE_PROFILES],
        "profiles": profiles,
    }


def test_phase11_population_uses_the_canonical_profile_count() -> None:
    profiles = benchmark_profiles()

    assert benchmark.PROFILE_VARIANTS_PER_CELL == 25
    assert benchmark.EXPECTED_PROFILE_COUNT == 375
    assert len(profiles) == benchmark.EXPECTED_PROFILE_COUNT


def test_phase11_population_covers_every_supported_cell() -> None:
    profiles = benchmark_profiles()

    assert len(SUPPORTED_MATRIX) == 15
    assert Counter((item.experience_level.value, item.resistance_days) for item in profiles) == {
        cell: benchmark.PROFILE_VARIANTS_PER_CELL for cell in SUPPORTED_MATRIX
    }


def test_phase11_population_covers_goals_equipment_and_official_durations() -> None:
    profiles = benchmark_profiles()

    assert len({item.goal.value for item in profiles}) >= 5
    assert len({item.equipment_label for item in profiles}) >= 4
    assert {item.duration_minutes for item in profiles} == set(OFFICIAL_SESSION_DURATIONS)


def test_phase11_population_covers_wrist_and_multiple_major_priorities() -> None:
    profiles = benchmark_profiles()

    cautions = {caution for item in profiles for caution in item.training_cautions}
    priorities = {muscle for item in profiles for muscle in item.priority_muscles}

    assert TrainingCaution.WRIST in cautions
    assert benchmark.MAJOR_MUSCLES.issubset(priorities)


def test_benchmark_template_setup_matches_the_exact_active_seed_library(db: Session) -> None:
    seed_exercises(db)
    references = benchmark._prepare_template_library(db)
    stale = db.scalar(
        select(TrainingProgramTemplate).where(
            TrainingProgramTemplate.slug == benchmark.EXPECTED_TEMPLATE_SLUGS[0]
        )
    )
    assert stale is not None
    stale.slug = "stale-prompt5-managed-template"
    db.commit()

    references = benchmark._prepare_template_library(db)

    assert len(references) == benchmark.EXPECTED_TEMPLATE_COUNT == 49
    assert tuple(sorted(item.slug for item in references)) == benchmark.EXPECTED_TEMPLATE_SLUGS
    assert db.get(TrainingProgramTemplate, stale.id).is_active is False


def test_closeout_verifier_accepts_a_fully_reconciled_payload() -> None:
    assert benchmark.verify_closeout(_valid_closeout_payload()) == ()


def test_closeout_verifier_enforces_category_and_unsat_totals() -> None:
    payload = _valid_closeout_payload()
    aggregate = cast(dict[str, object], payload["aggregate"])
    counts = cast(dict[str, int], aggregate["category_counts"])
    counts["PASS"] -= 1
    counts["UNSATISFIED"] = 1
    profiles = cast(list[dict[str, object]], payload["profiles"])
    profiles[0]["category"] = "UNSATISFIED"

    blockers = benchmark.verify_closeout(payload)

    assert any("UNSAT classifications" in blocker for blocker in blockers)


def test_closeout_verifier_enforces_the_determinism_denominator() -> None:
    payload = _valid_closeout_payload()
    determinism = cast(dict[str, object], payload["determinism"])
    determinism["cases"] = benchmark.EXPECTED_PROFILE_COUNT - 1

    assert any("Determinism denominator" in item for item in benchmark.verify_closeout(payload))


def test_recovered_template_attempt_is_not_a_final_semantic_failure() -> None:
    payload = _valid_closeout_payload()
    profiles = cast(list[dict[str, object]], payload["profiles"])
    profiles[0]["template"] = {
        "recovered_with_alternative": True,
        "attempted_templates": ({"status": "rejected"}, {"status": "succeeded"}),
    }

    assert benchmark.verify_closeout(payload) == ()


def test_quality_issue_cannot_disappear_from_aggregate_reporting() -> None:
    payload = _valid_closeout_payload()
    profiles = cast(list[dict[str, object]], payload["profiles"])
    profiles[0]["category"] = "QUALITY_ISSUE"
    profiles[0]["audit_findings"] = [
        {
            "code": "MISSING_MAJOR_MUSCLE_COVERAGE",
            "severity": "quality",
            "classification": "B",
        }
    ]
    aggregate = cast(dict[str, object], payload["aggregate"])
    counts = cast(dict[str, int], aggregate["category_counts"])
    counts["PASS"] -= 1
    counts["QUALITY_ISSUE"] = 1

    assert any("quality-code audit" in item for item in benchmark.verify_closeout(payload))


def test_unexplained_final_semantic_failure_blocks_ready() -> None:
    payload = _valid_closeout_payload()
    aggregate = cast(dict[str, object], payload["aggregate"])
    quality = cast(dict[str, object], aggregate["quality"])
    semantic = cast(dict[str, int], quality["semantic_substitution"])
    semantic["unexplained_final_semantic_failures"] = 1

    assert any("semantic" in item.lower() for item in benchmark.verify_closeout(payload))


@pytest.mark.parametrize(
    ("section", "key"),
    (
        ("category_counts", "ENGINE_BUG"),
        ("quality", "equipment_violations_custom"),
        ("quality", "safety_violations_custom"),
        ("quality", "redundancy_violations_custom"),
    ),
)
def test_any_hard_acceptance_failure_blocks_ready(section: str, key: str) -> None:
    payload = deepcopy(_valid_closeout_payload())
    aggregate = cast(dict[str, object], payload["aggregate"])
    target = cast(dict[str, int], aggregate[section])
    target[key] = 1
    if section == "category_counts":
        target["PASS"] -= 1

    assert benchmark.verify_closeout(payload)


def test_complete_under_budget_session_is_not_a_duration_quality_issue() -> None:
    assert (
        benchmark._duration_policy_failure(
            requested_minutes=60,
            estimated_total_minutes=42,
            main_exercises=5,
            minimum_exercises=5,
            reason_codes=("SESSION_DURATION_TARGET_SATISFIED",),
        )
        is None
    )


def test_unjustified_over_budget_session_is_a_duration_quality_issue() -> None:
    assert (
        benchmark._duration_policy_failure(
            requested_minutes=60,
            estimated_total_minutes=90,
            main_exercises=5,
            minimum_exercises=5,
            reason_codes=(),
        )
        == "above_maximum"
    )


def test_unsat_classification_uses_the_final_result_cause() -> None:
    catalog_limited = SimpleNamespace(
        program=None,
        error_code=SimpleNamespace(value="NO_AVAILABLE_EQUIPMENT_MATCH"),
        errors=("NO_ELIGIBLE_EXERCISES",),
    )
    constrained = SimpleNamespace(
        program=None,
        error_code=SimpleNamespace(value="UNSATISFIED_CONSTRAINT"),
        errors=(
            "PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED",
            "REQUIRED_SLOT_HARD_IMPOSSIBILITY",
        ),
    )

    catalog = benchmark._classify_final_unsat(cast(ProgramGenerationResult, catalog_limited))
    constraint = benchmark._classify_final_unsat(cast(ProgramGenerationResult, constrained))

    assert catalog["cause"] == "legitimate catalog limitation"
    assert constraint["cause"] == "legitimate constraint limitation"
    assert catalog["evidence"] == (
        "NO_AVAILABLE_EQUIPMENT_MATCH",
        "NO_ELIGIBLE_EXERCISES",
    )


def test_semantic_audit_distinguishes_valid_recovered_and_legitimate_no_valid() -> None:
    result = SimpleNamespace(
        program=SimpleNamespace(
            aggregate_metrics={
                "substitution_successes": 3,
                "substitution_no_valid_replacement": 2,
                "relaxed_required_slots": ({"patterns": ("squat",)},),
            },
            validation_report=SimpleNamespace(
                warnings=("SEMANTIC_SLOT_MISMATCH_SELECTED",),
                errors=(),
            ),
            weekly_schedule=(),
            decision_trace=(
                {
                    "stage": "substitution_observability",
                    "decisions": (
                        {"cause": "display_alternative", "alternative_exercise_ids": ()},
                        {"cause": "volume_repair", "alternative_exercise_ids": ()},
                        {"cause": "volume_repair", "alternative_exercise_ids": ("valid",)},
                    ),
                },
            ),
        )
    )
    template = {
        "succeeded": True,
        "recovered_with_alternative": True,
        "attempted_templates": (
            {"status": "rejected"},
            {"status": "succeeded"},
        ),
    }

    audit = benchmark._semantic_substitution_audit(cast(ProgramGenerationResult, result), template)

    assert audit == {
        "successful_valid_substitutions": 3,
        "recovered_intermediate_attempts": 2,
        "legitimate_no_valid_replacements": 1,
        "final_semantic_degradations": 1,
        "explained_final_semantic_degradations": 1,
        "unexplained_final_semantic_failures": 0,
    }


def test_semantic_warning_without_final_evidence_is_unexplained() -> None:
    result = SimpleNamespace(
        program=SimpleNamespace(
            aggregate_metrics={
                "substitution_successes": 0,
                "substitution_no_valid_replacement": 0,
            },
            validation_report=SimpleNamespace(
                warnings=("SEMANTIC_SLOT_MISMATCH_SELECTED",),
                errors=(),
            ),
            weekly_schedule=(),
            decision_trace=(),
        )
    )

    audit = benchmark._semantic_substitution_audit(
        cast(ProgramGenerationResult, result), {"succeeded": False}
    )

    assert audit["unexplained_final_semantic_failures"] == 1


def test_closeout_report_contains_the_authoritative_library_and_one_verdict() -> None:
    report = render_report(_valid_closeout_payload(), verification_summary=("focused: pass",))

    assert f"Profiles: {benchmark.EXPECTED_PROFILE_COUNT}" in report
    assert f"Active templates: {benchmark.EXPECTED_TEMPLATE_COUNT}" in report
    assert benchmark.EXPECTED_TEMPLATE_SLUGS[0] in report
    assert "Catalog hash: " in report
    assert "Template hash: " in report
    assert report.count("READY FOR PROMPT 6") == 1


def test_phase11_negative_profiles_reject_unsupported_days() -> None:
    for profile in NEGATIVE_PROFILES:
        result = generate_program(
            profile_to_request(profile, enforce_matrix=False), full_catalog(), RULESET
        )

        assert result.program is None
        assert result.error_code is not None
        assert result.error_code.value == "UNSUPPORTED_RESISTANCE_TRAINING_DAYS"


def test_phase11_representative_output_has_an_identical_determinism_fingerprint() -> None:
    profile = benchmark_profiles()[37]
    request = profile_to_request(profile)
    first = generate_program(request, full_catalog(), RULESET)
    second = generate_program(request, full_catalog(), RULESET)

    assert canonical_fingerprint(first) == canonical_fingerprint(second)


def test_fallback_construction_does_not_replace_quality_outcome() -> None:
    result = _successful_result()
    program_result = cast(ProgramGenerationResult, result)

    assert benchmark._category(program_result, {"fallback_succeeded": True}, ()) == "PASS"
    assert benchmark._construction_path(program_result, {"succeeded": False}) == "FALLBACK"


def test_legitimate_constraint_finding_is_pass_with_constraints() -> None:
    result = _successful_result(warnings=("BODY_ANALYSIS_PRIORITY_PARTIAL",))

    category = benchmark._category(
        cast(ProgramGenerationResult, result),
        {"fallback_succeeded": False},
        (
            {
                "code": "BODY_ANALYSIS_PRIORITY_PARTIAL",
                "severity": "constraint",
                "message": "hamstrings",
            },
        ),
    )

    assert category == "PASS_WITH_CONSTRAINTS"


def test_weekly_pattern_frequency_is_not_automatically_redundant() -> None:
    repeated_pattern_days = tuple(
        SimpleNamespace(
            exercises=(
                SimpleNamespace(
                    exercise_id=uuid4(),
                    primary_muscle="chest",
                    movement_pattern="horizontal_push",
                    exercise_type="compound",
                    equipment=frozenset({"dumbbell"}),
                ),
            )
        )
        for _ in range(4)
    )

    detector = getattr(benchmark, "_has_redundant_near_identical_movements", None)

    assert callable(detector)
    assert detector(repeated_pattern_days) is False


def test_same_session_exact_duplicate_is_redundant() -> None:
    exercise_id = uuid4()
    duplicated_day = SimpleNamespace(
        exercises=tuple(
            SimpleNamespace(
                exercise_id=exercise_id,
                primary_muscle="chest",
                movement_pattern="horizontal_push",
                exercise_type="compound",
                equipment=frozenset({"dumbbell"}),
            )
            for _ in range(2)
        )
    )

    detector = getattr(benchmark, "_has_redundant_near_identical_movements", None)

    assert callable(detector)
    assert detector((duplicated_day,)) is True


def test_two_similar_same_session_movements_are_not_automatically_redundant() -> None:
    similar_day = SimpleNamespace(
        exercises=tuple(
            SimpleNamespace(
                exercise_id=uuid4(),
                primary_muscle="chest",
                movement_pattern="horizontal_push",
                exercise_type="compound",
                equipment=frozenset({"dumbbell"}),
            )
            for _ in range(2)
        )
    )

    assert benchmark._has_redundant_near_identical_movements((similar_day,)) is False


def test_major_coverage_uses_the_canonical_profile_minimum_not_two_sets() -> None:
    ranges = {
        muscle.value: {
            "minimum_coverage_required": True,
            "minimum_effective_sets": 1,
            "actual_effective_volume": 1.0,
        }
        for muscle in benchmark.MAJOR_MUSCLES
    }

    assert benchmark._missing_major_muscle_coverage(ranges) == ()


def test_supplemental_abs_absence_is_not_a_major_coverage_miss() -> None:
    ranges = {
        MuscleGroup.ABS.value: {
            "minimum_coverage_required": True,
            "minimum_effective_sets": 1,
            "actual_effective_volume": 0.0,
        }
    }

    assert benchmark._missing_major_muscle_coverage(ranges) == ()
