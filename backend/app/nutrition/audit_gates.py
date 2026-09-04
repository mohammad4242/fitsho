"""Deterministic aggregation and acceptance gates for nutrition generation audits."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from statistics import mean
from typing import Any

AUDIT_SCHEMA_VERSION = "nutrition-generation-audit-v2"
FROZEN_HOLDOUT_DEFINITION_VERSION = "nutrition-holdout-definition-v1"


def summarize_audit(records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = tuple(records)
    automatic = tuple(row for row in rows if _automatically_eligible(row))
    successes = tuple(row for row in automatic if row.get("outcome") == "success")
    safe_resolutions = sum(
        row.get("outcome") == "success" if _automatically_eligible(row) else _safe_block(row)
        for row in rows
    )
    failure_histogram: Counter[str] = Counter()
    candidate_failure_histogram: Counter[str] = Counter()
    selection_changed = 0
    quality_comparisons: list[bool] = []
    for row in automatic:
        if row.get("outcome") != "success":
            for code in row.get("reason_codes", ()):
                failure_histogram[str(code)] += 1
            trace = _selection_trace(row)
            candidate_histogram = trace.get("failure_reason_counts", {})
            if isinstance(candidate_histogram, Mapping):
                for code, count in candidate_histogram.items():
                    candidate_failure_histogram[str(code)] += int(count)
        trace = _selection_trace(row)
        if trace.get("selected_differs_from_first_valid") is True:
            selection_changed += 1
        comparison = trace.get("selected_quality_not_worse_than_first_valid")
        if isinstance(comparison, bool):
            quality_comparisons.append(comparison)

    violations = Counter(
        str(code) for row in rows for code in row.get("safety_invariant_violations", ())
    )
    return {
        "total_profiles": len(rows),
        "automatically_eligible_count": len(automatic),
        "automatically_eligible_success_count": len(successes),
        "automatically_eligible_failure_count": len(automatic) - len(successes),
        "automatically_eligible_success_rate": _rate(len(successes), len(automatic)),
        "safe_resolution_count": safe_resolutions,
        "safe_resolution_rate": _rate(safe_resolutions, len(rows)),
        "failure_histogram": dict(sorted(failure_histogram.items())),
        "candidate_failure_histogram": dict(sorted(candidate_failure_histogram.items())),
        "selection_changed_count": selection_changed,
        "selection_changed_rate": _rate(selection_changed, len(automatic)),
        "selection_quality_not_worse_count": sum(quality_comparisons),
        "selection_quality_comparison_count": len(quality_comparisons),
        "safety_invariant_violation_counts": dict(sorted(violations.items())),
        "cohorts": _cohort_breakdown(automatic),
        "performance": _performance(rows),
        "acceptance": {
            "safety_invariants_passed": not violations,
            "selection_quality_never_worse": all(quality_comparisons),
            "automatically_eligible_success_over_90_percent": _rate(len(successes), len(automatic))
            > 90.0,
            "safe_resolution_100_percent": safe_resolutions == len(rows),
        },
    }


def _automatically_eligible(row: Mapping[str, Any]) -> bool:
    spec = row.get("spec", {})
    if not isinstance(spec, Mapping):
        return True
    flags = spec.get("safety_flags", {})
    return not spec.get("medical_conditions") and not any(value is True for value in flags.values())


def _safe_block(row: Mapping[str, Any]) -> bool:
    return row.get("outcome") in {
        "safety_blocked",
        "physician_manual_plan_required",
    }


def _selection_trace(row: Mapping[str, Any]) -> Mapping[str, Any]:
    diagnostics = row.get("diagnostics", {})
    if not isinstance(diagnostics, Mapping):
        return {}
    trace = diagnostics.get("selection_trace", {})
    return trace if isinstance(trace, Mapping) else {}


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator * 100.0, 2) if denominator else 0.0


def _performance(records: tuple[Mapping[str, Any], ...]) -> dict[str, float]:
    values = sorted(
        float(row["generation_latency_ms"])
        for row in records
        if row.get("generation_latency_ms") is not None
    )
    if not values:
        return {
            "mean_generation_latency_ms": 0.0,
            "p50_generation_latency_ms": 0.0,
            "p95_generation_latency_ms": 0.0,
            "max_generation_latency_ms": 0.0,
        }
    return {
        "mean_generation_latency_ms": round(mean(values), 3),
        "p50_generation_latency_ms": _percentile(values, 0.50),
        "p95_generation_latency_ms": _percentile(values, 0.95),
        "max_generation_latency_ms": values[-1],
    }


def _percentile(values: list[float], percentile: float) -> float:
    index = max(0, min(len(values) - 1, int(len(values) * percentile + 0.999999) - 1))
    return values[index]


def _cohort_breakdown(records: tuple[Mapping[str, Any], ...]) -> dict[str, dict[str, Any]]:
    dimensions = (
        "dietary_pattern",
        "budget_style",
        "fitness_goal",
        "exercise_type",
        "meals_per_day",
        "snacks_per_day",
        "cooking_skill",
        "cooking_time_minutes",
    )
    result: dict[str, dict[str, Any]] = {}
    for dimension in dimensions:
        groups: defaultdict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in records:
            spec = row.get("spec", {})
            if isinstance(spec, Mapping) and dimension in spec:
                groups[str(spec[dimension])].append(row)
        result[dimension] = {
            value: {
                "sample_size": len(group),
                "success_count": sum(row.get("outcome") == "success" for row in group),
                "success_rate": _rate(
                    sum(row.get("outcome") == "success" for row in group), len(group)
                ),
                "meaningful_sample": len(group) >= 5,
            }
            for value, group in sorted(groups.items())
        }
    return result
