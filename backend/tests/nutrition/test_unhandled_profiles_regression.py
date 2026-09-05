import pytest

from scripts.audit_nutrition_engine_100_profiles import DEFAULT_DB_URL, run_100_profiles_audit

BASELINE_UNHANDLED_INDICES = [
    6,
    20,
    22,
    24,
    30,
    33,
    36,
    42,
    50,
    54,
    59,
    61,
    64,
    65,
    88,
    92,
    95,
    99,
    100,
]


@pytest.mark.parametrize("profile_index", BASELINE_UNHANDLED_INDICES)
def test_baseline_unhandled_profiles_no_uncaught_exception(profile_index: int) -> None:
    records = run_100_profiles_audit(
        DEFAULT_DB_URL,
        seed=20260903,
        count=100,
        profile_index=profile_index,
    )
    assert len(records) == 1
    record = records[0]
    assert record.outcome != "failed"
    assert "UNHANDLED_ENGINE_ERROR" not in record.reason_codes
    assert record.outcome in ("success", "infeasible", "target_infeasible", "safety_blocked")
