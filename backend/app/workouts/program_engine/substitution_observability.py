"""Small, stable observability helpers for substitution decisions."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.workouts.program_engine.substitution_engine import SubstitutionDecision


SUBSTITUTION_METRIC_KEYS = (
    "substitution_requests",
    "substitution_successes",
    "substitution_exact_group",
    "substitution_exact_semantic_role",
    "substitution_muscle_focus_preserved",
    "substitution_role_preserved_focus_degraded",
    "substitution_movement_family_fallback",
    "substitution_equipment_triggered",
    "substitution_constraint_triggered",
    "substitution_no_valid_replacement",
)

_CONSTRAINT_CAUSES = frozenset(
    {
        "safety",
        "axial_load",
        "balance",
        "overhead",
        "range_of_motion",
    }
)


def substitution_observability(decision: SubstitutionDecision) -> dict[str, int]:
    """Return deterministic one-request counters for a substitution decision."""
    metrics = {key: 0 for key in SUBSTITUTION_METRIC_KEYS}
    options = decision.options
    metrics["substitution_requests"] = 1
    metrics["substitution_successes"] = int(bool(options))
    metrics["substitution_no_valid_replacement"] = int(not options)
    metrics["substitution_equipment_triggered"] = int(decision.cause.value == "missing_equipment")
    metrics["substitution_constraint_triggered"] = int(decision.cause.value in _CONSTRAINT_CAUSES)
    metrics["substitution_exact_group"] = int(
        any("SUBSTITUTION_SAME_GROUP" in option.reason_codes for option in options)
    )
    metrics["substitution_exact_semantic_role"] = int(
        any("SUBSTITUTION_EXACT_ROLE" in option.reason_codes for option in options)
    )
    metrics["substitution_muscle_focus_preserved"] = int(
        any("SUBSTITUTION_MUSCLE_FOCUS_PRESERVED" in option.reason_codes for option in options)
    )
    metrics["substitution_role_preserved_focus_degraded"] = int(
        any(
            "SUBSTITUTION_ROLE_PRESERVED_FOCUS_DEGRADED" in option.reason_codes
            for option in options
        )
    )
    metrics["substitution_movement_family_fallback"] = int(
        any("SUBSTITUTION_MOVEMENT_FAMILY_FALLBACK" in option.reason_codes for option in options)
    )
    return metrics


def substitution_trace_entry(decision: SubstitutionDecision) -> dict[str, object]:
    """Return a decision-trace entry suitable for an existing program trace."""
    return {
        "stage": "substitution",
        "target_exercise_id": str(decision.target_exercise_id),
        "cause": decision.cause.value,
        "alternative_count": len(decision.options),
        "metrics": substitution_observability(decision),
        "reason_codes": decision.reason_codes,
    }


def merge_substitution_observability(
    current: dict[str, object], decision: SubstitutionDecision
) -> dict[str, object]:
    """Add one decision's counters to an existing aggregate metrics mapping."""
    merged = dict(current)
    observation = substitution_observability(decision)
    for key, value in observation.items():
        previous = merged.get(key, 0)
        merged[key] = (previous if isinstance(previous, int) else 0) + value
    return merged


def aggregate_substitution_observability(
    decisions: Iterable[SubstitutionDecision],
) -> dict[str, object]:
    """Summarize decisions for aggregate metrics."""
    aggregate: dict[str, object] = {key: 0 for key in SUBSTITUTION_METRIC_KEYS}
    for decision in decisions:
        aggregate = merge_substitution_observability(aggregate, decision)
    return aggregate


def substitution_decision_summaries(
    decisions: Iterable[SubstitutionDecision],
) -> tuple[dict[str, object], ...]:
    """Return compact target/alternative pairs for the decision trace only."""
    return tuple(
        {
            "target_exercise_id": str(decision.target_exercise_id),
            "cause": decision.cause.value,
            "alternative_exercise_ids": tuple(str(item) for item in decision.exercise_ids),
        }
        for decision in decisions
    )
