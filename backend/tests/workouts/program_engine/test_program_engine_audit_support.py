import json
from types import SimpleNamespace

from app.profile.enums import ExperienceLevel
from app.workouts.program_engine.enums import SplitType
from app.workouts.program_engine.schemas import ProgramGenerationResult, SplitPlan
from scripts.audit_supported_profile_catalog import audit_supported_catalog
from scripts.generate_200_profiles_eval import generate_200_supported_profiles
from scripts.program_engine_audit_support import (
    build_profile_audit_record,
    classify_profile_support,
    profile_fingerprint,
    summarize_audit_results,
    write_audit_json,
)


def _profile(
    *,
    experience_level: ExperienceLevel = ExperienceLevel.INTERMEDIATE,
    training_days_per_week: int = 4,
) -> SimpleNamespace:
    return SimpleNamespace(
        index=1,
        name="آزمون",
        experience_level=experience_level,
        training_days_per_week=training_days_per_week,
        session_duration_minutes=60,
    )


def test_supported_denominator_uses_production_compatibility_rules() -> None:
    supported = classify_profile_support(_profile())
    unsupported = classify_profile_support(
        _profile(experience_level=ExperienceLevel.FIRST_MONTH, training_days_per_week=5)
    )

    assert supported.supported is True
    assert supported.cohort == "supported"
    assert unsupported.supported is False
    assert unsupported.cohort == "unsupported"
    assert unsupported.reason_codes == ("UNSUPPORTED_RESISTANCE_TRAINING_DAYS",)


def test_unsupported_profiles_are_separate_from_the_success_denominator() -> None:
    supported = classify_profile_support(_profile())
    unsupported = classify_profile_support(
        _profile(experience_level=ExperienceLevel.ADVANCED, training_days_per_week=2)
    )
    results = [
        build_profile_audit_record(
            _profile(), supported, status="SUCCESS", failure_info=None
        ),
        build_profile_audit_record(
            _profile(), supported, status="FAILED", failure_info={"root_cause": "CATALOG_GAP"}
        ),
        build_profile_audit_record(
            _profile(experience_level=ExperienceLevel.ADVANCED, training_days_per_week=2),
            unsupported,
            status="FAILED",
            failure_info={"root_cause": "UNSUPPORTED_RESISTANCE_TRAINING_DAYS"},
        ),
    ]

    summary = summarize_audit_results(results)

    assert summary["supported_attempted"] == 2
    assert summary["supported_success"] == 1
    assert summary["supported_failure"] == 1
    assert summary["supported_success_rate"] == 50.0
    assert summary["unsupported_negative_cohort"] == 1


def test_catalog_gap_supported_failure_remains_in_supported_denominator() -> None:
    profile = _profile()
    support = classify_profile_support(profile)

    record = build_profile_audit_record(
        profile,
        support,
        status="FAILED",
        failure_info={"root_cause": "CATALOG_GAP", "all_errors": ["NO_SAFE_EXERCISE"]},
    )

    summary = summarize_audit_results([record])

    assert record["supported"] is True
    assert record["cohort"] == "supported"
    assert summary["supported_attempted"] == 1
    assert summary["supported_success"] == 0
    assert summary["supported_failure"] == 1
    assert summary["unsupported_negative_cohort"] == 0


def test_profile_fingerprint_is_stable_and_input_sensitive() -> None:
    profile = _profile()
    equivalent = _profile()
    changed = _profile(training_days_per_week=3)

    assert profile_fingerprint(profile) == profile_fingerprint(equivalent)
    assert profile_fingerprint(profile) != profile_fingerprint(changed)
    assert len(profile_fingerprint(profile)) == 64


def test_profile_audit_record_is_json_safe() -> None:
    profile = _profile()
    support = classify_profile_support(profile)
    record = build_profile_audit_record(
        profile,
        support,
        status="FAILED",
        failure_info={"root_cause": "CATALOG_GAP"},
    )

    json.dumps(record, default=str, sort_keys=True)


def test_write_audit_json_is_the_serialized_source_of_truth(tmp_path) -> None:
    profile = _profile()
    support = classify_profile_support(profile)
    record = build_profile_audit_record(profile, support, status="SUCCESS")
    output = tmp_path / "audit.json"

    write_audit_json([record], output)
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert isinstance(payload, list)
    assert isinstance(payload[0]["profile"], dict)
    assert payload[0]["profile_fingerprint"] == profile_fingerprint(profile)


def test_catalog_audit_keeps_supported_catalog_gap_as_a_failure() -> None:
    supported = _profile()
    unsupported = _profile(
        experience_level=ExperienceLevel.FIRST_MONTH,
        training_days_per_week=5,
    )

    records = audit_supported_catalog(
        [supported, unsupported],
        eligible_count_for_profile=lambda profile: 0,
    )

    assert records[0]["supported"] is True
    assert records[0]["catalog_gap"] is True
    assert records[0]["status"] == "FAILED"
    assert records[1]["cohort"] == "unsupported"


def test_200_supported_profile_cohort_is_deterministic_and_exact() -> None:
    first = generate_200_supported_profiles(seed=20260901)
    second = generate_200_supported_profiles(seed=20260901)

    assert len(first) == 200
    assert all(classify_profile_support(profile).supported for profile in first)
    assert [profile_fingerprint(profile) for profile in first] == [
        profile_fingerprint(profile) for profile in second
    ]


def test_audit_record_exposes_selection_quality_and_candidate_metrics() -> None:
    profile = _profile()
    support = classify_profile_support(profile)
    selection_trace = {
        "stage": "final_program_selection",
        "schema_version": "program_selection_v1",
        "selection_phase": "dynamic_fallback",
        "selection_strategy": "lexicographic_max_min_quality",
        "proposed_candidate_count": 7,
        "evaluated_candidate_count": 7,
        "successful_candidate_count": 2,
        "admitted_candidate_count": 1,
        "evidence_rejected_count": 1,
        "first_valid_identifier": "dynamic_fallback:first",
        "selected_identifier": "dynamic_fallback:second",
        "selected_source": "dynamic_fallback",
        "selected_preconstruction_rank": 2,
        "selected_different_from_first_valid": True,
        "first_valid_quality_key": {"critical_dimensions": {"volume": 70.0}},
        "summarized_quality_key": {
            "critical_dimensions": {"volume": 95.0},
            "coverage_percentage": 100.0,
            "volume_floor": 95.0,
            "explicit_priority_floor": None,
            "body_analysis_priority_floor": None,
            "recovery_margin": 100.0,
            "duration_fit": 100.0,
        },
        "selected_quality_not_worse_than_first_valid": True,
        "warning_burden": {"repairable": 0, "soft": 1},
        "repair_burden": {"structural": 0, "workload": 1, "scheduling": 0, "total": 1},
        "substitution_burden": 2,
    }
    program = SimpleNamespace(
        split=SplitPlan(
            split_type=SplitType.DYNAMIC_FALLBACK,
            day_focuses=("a", "b", "c", "d"),
            weekdays=(0, 1, 2, 3),
            score=-1000,
            reason_codes=(),
        ),
        weekly_schedule=(),
        decision_trace=(selection_trace,),
        aggregate_metrics={},
    )

    record = build_profile_audit_record(
        profile,
        support,
        status="SUCCESS",
        result=ProgramGenerationResult(program=program),
        runtime_ms=12.5,
    )

    assert record["candidate_counts"] == {
        "proposed": 7,
        "evaluated": 7,
        "successful": 2,
        "admitted": 1,
        "evidence_rejected": 1,
    }
    assert record["selected_source"] == "dynamic_fallback"
    assert record["critical_quality_floor"] == 95.0
    assert record["selected_quality_not_worse_than_first_valid"] is True
