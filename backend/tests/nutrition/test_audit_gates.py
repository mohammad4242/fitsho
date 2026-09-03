from dataclasses import asdict

from app.nutrition.audit_gates import summarize_audit


def _record(
    *,
    index: int,
    outcome: str,
    safety_blocked: bool = False,
    selected_changed: bool | None = None,
) -> dict[str, object]:
    return {
        "spec": {
            "index": index,
            "dietary_pattern": "omnivore",
            "budget_style": "strict",
            "fitness_goal": "maintain_weight",
            "exercise_type": "resistance",
            "meals_per_day": 3,
            "snacks_per_day": 1,
            "cooking_skill": "basic",
            "cooking_time_minutes": 30,
            "allergies": [],
            "intolerances": [],
            "medical_conditions": ["blocked"] if safety_blocked else [],
            "safety_flags": {"pregnant": safety_blocked},
        },
        "outcome": outcome,
        "reason_codes": ["STRICT_BUDGET_NO_FEASIBLE_REPAIR"] if outcome != "success" else [],
        "diagnostics": {
            "selection_trace": {
                "first_valid_program_code": "P01" if outcome == "success" else None,
                "selected_program_code": "P02" if selected_changed else "P01",
                "selected_differs_from_first_valid": selected_changed,
                "selected_quality": {"core_nutrition_max_deviation": "0"},
                "first_valid_quality": {"core_nutrition_max_deviation": "0"},
                "candidates": [{"outcome": "success"}] if outcome == "success" else [],
            }
        },
        "generation_latency_ms": float(index),
        "safety_invariant_violations": [],
    }


def test_audit_summary_reports_eligibility_selection_failures_and_latency() -> None:
    records = [
        _record(index=1, outcome="success", selected_changed=True),
        _record(index=2, outcome="success"),
        _record(index=3, outcome="failed"),
        _record(index=4, outcome="safety_blocked", safety_blocked=True),
    ]

    summary = summarize_audit(records)

    assert summary["automatically_eligible_count"] == 3
    assert summary["automatically_eligible_success_count"] == 2
    assert summary["safe_resolution_count"] == 3
    assert summary["selection_changed_count"] == 1
    assert summary["failure_histogram"] == {"STRICT_BUDGET_NO_FEASIBLE_REPAIR": 1}
    assert summary["performance"]["mean_generation_latency_ms"] == 2.5
    assert summary["performance"]["p95_generation_latency_ms"] == 4.0


def test_audit_summary_keeps_invariant_violations_visible() -> None:
    record = _record(index=1, outcome="success")
    record["safety_invariant_violations"] = ["STRICT_BUDGET_VIOLATION"]

    summary = summarize_audit([record])

    assert summary["safety_invariant_violation_counts"] == {"STRICT_BUDGET_VIOLATION": 1}
    assert summary["acceptance"]["safety_invariants_passed"] is False


def test_profile_generation_is_reproducible_for_a_fixed_seed() -> None:
    from scripts.run_nutrition_100_profiles_audit import generate_100_profiles

    first = [asdict(profile) for profile in generate_100_profiles(seed=20261017, count=5)]
    second = [asdict(profile) for profile in generate_100_profiles(seed=20261017, count=5)]

    assert first == second
