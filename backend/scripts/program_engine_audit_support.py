"""Shared, reproducible evidence helpers for Program Engine audits."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from statistics import median
from typing import Any, Literal
from uuid import UUID

from app.profile.training_compatibility import (
    ResistanceTrainingDayStatus,
    UnsupportedResistanceTrainingCombinationError,
    require_supported_resistance_training_days,
)

AUDIT_SCHEMA_VERSION = "program_engine_audit_v1"
SUPPORTED_COHORT: Literal["supported"] = "supported"
UNSUPPORTED_COHORT: Literal["unsupported"] = "unsupported"


@dataclass(frozen=True)
class ProfileSupport:
    supported: bool
    cohort: Literal["supported", "unsupported"]
    status: str
    reason_codes: tuple[str, ...] = ()


def classify_profile_support(profile: Any) -> ProfileSupport:
    """Classify a profile only with the production compatibility rule."""

    experience_level = profile.experience_level
    training_days = profile.training_days_per_week
    try:
        status = require_supported_resistance_training_days(experience_level, training_days)
    except UnsupportedResistanceTrainingCombinationError:
        return ProfileSupport(
            supported=False,
            cohort=UNSUPPORTED_COHORT,
            status=ResistanceTrainingDayStatus.UNSUPPORTED.value,
            reason_codes=("UNSUPPORTED_RESISTANCE_TRAINING_DAYS",),
        )
    return ProfileSupport(
        supported=True,
        cohort=SUPPORTED_COHORT,
        status=status.value,
    )


def supported_profile_cohort(
    profile_factory: Callable[[int], Sequence[Any]],
    *,
    count: int,
    seed: int,
) -> list[Any]:
    """Build a deterministic cohort containing exactly ``count`` supported profiles."""

    if count < 0:
        raise ValueError("count must be non-negative")
    profiles: list[Any] = []
    batch_seed = seed
    while len(profiles) < count:
        batch = profile_factory(batch_seed)
        if not batch:
            raise ValueError("profile factory produced no profiles")
        profiles.extend(
            profile for profile in batch if classify_profile_support(profile).supported
        )
        batch_seed += 1
        if batch_seed - seed > 1000:
            raise ValueError("profile factory could not produce enough supported profiles")
    return profiles[:count]


def profile_fingerprint(profile: Any) -> str:
    """Return a stable SHA-256 fingerprint of profile input values."""

    canonical = json.dumps(
        _json_safe(profile),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_profile_audit_record(
    profile: Any,
    support: ProfileSupport,
    *,
    status: str,
    result: Any = None,
    failure_info: Mapping[str, Any] | None = None,
    runtime_ms: float | None = None,
) -> dict[str, Any]:
    selection = extract_program_audit_metrics(result)
    failure = dict(failure_info) if failure_info is not None else None
    return {
        "audit_schema_version": AUDIT_SCHEMA_VERSION,
        "profile": profile,
        "profile_fingerprint": profile_fingerprint(profile),
        "cohort": support.cohort,
        "supported": support.supported,
        "support_status": support.status,
        "support_reason_codes": support.reason_codes,
        "status": status,
        "runtime_ms": round(runtime_ms, 3) if runtime_ms is not None else None,
        "failure_info": failure,
        "failure_family": failure_family(failure, result),
        **selection,
    }


def extract_program_audit_metrics(result: Any) -> dict[str, Any]:
    """Extract bounded selection and quality evidence from a generation result."""

    program = getattr(result, "program", None) if result is not None else None
    trace = _trace_for_result(result, program)
    selection_trace = _latest_stage(trace, "final_program_selection")
    quality = _quality_from_selection_trace(selection_trace, program)
    selected_identifier = _string_or_none(selection_trace.get("selected_identifier"))
    selected_source = _string_or_none(selection_trace.get("selected_source"))
    selected_rank = selection_trace.get("selected_preconstruction_rank")
    counts = {
        "proposed": _integer_or_zero(selection_trace.get("proposed_candidate_count")),
        "evaluated": _integer_or_zero(selection_trace.get("evaluated_candidate_count")),
        "successful": _integer_or_zero(selection_trace.get("successful_candidate_count")),
        "admitted": _integer_or_zero(selection_trace.get("admitted_candidate_count")),
        "evidence_rejected": _integer_or_zero(
            selection_trace.get("evidence_rejected_count")
        ),
    }
    phase = _string_or_none(selection_trace.get("selection_phase"))
    selected_split = _enum_value(getattr(getattr(program, "split", None), "split_type", None))
    return {
        "selection_phase": phase,
        "selection_strategy": _string_or_none(selection_trace.get("selection_strategy")),
        "candidate_counts": counts,
        "proposed_candidates": counts["proposed"],
        "evaluated_candidates": counts["evaluated"],
        "successful_candidates": counts["successful"],
        "admitted_candidates": counts["admitted"],
        "evidence_rejected_candidates": counts["evidence_rejected"],
        "primary_candidates_evaluated": counts["evaluated"] if phase == "primary" else 0,
        "dynamic_candidates_evaluated": counts["evaluated"] if phase == "dynamic_fallback" else 0,
        "first_valid_identifier": _string_or_none(
            selection_trace.get("first_valid_identifier")
        ),
        "selected_identifier": selected_identifier,
        "selected_source": selected_source,
        "selected_preconstruction_rank": (
            selected_rank if isinstance(selected_rank, int) else None
        ),
        "selected_candidate_source": selected_source,
        "selected_candidate_identifier": selected_identifier,
        "selected_candidate_preconstruction_rank": (
            selected_rank if isinstance(selected_rank, int) else None
        ),
        "selected_candidate_preconstruction_score": _selected_split_score(program),
        "selected_different_from_first_valid": bool(
            selection_trace.get("selected_different_from_first_valid", False)
        ),
        "first_valid_quality_key": _mapping_or_empty(
            selection_trace.get("first_valid_quality_key")
        ),
        "selected_quality_key": quality,
        "selected_quality_not_worse_than_first_valid": selection_trace.get(
            "selected_quality_not_worse_than_first_valid"
        ),
        "critical_quality_floor": _critical_quality_floor(quality),
        "coverage": _quality_value(quality, "coverage_percentage"),
        "volume": _quality_value(quality, "volume_floor"),
        "explicit_priority": _quality_value(quality, "explicit_priority_floor"),
        "body_analysis_priority": _quality_value(quality, "body_analysis_priority_floor"),
        "recovery": _quality_value(quality, "recovery_margin"),
        "duration": _quality_value(quality, "duration_fit"),
        "warning_burden": _json_safe(selection_trace.get("warning_burden", {})),
        "repair_burden": _json_safe(selection_trace.get("repair_burden", {})),
        "substitution_burden": _integer_or_zero(
            selection_trace.get("substitution_burden")
        ),
        "trace_size_bytes": _trace_size_bytes(selection_trace),
        "selection_trace": _json_safe(selection_trace) if selection_trace else None,
        "selected_split": selected_split,
        "selected_days": len(getattr(program, "weekly_schedule", ())) if program else 0,
    }


def summarize_audit_results(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize success only over the production-supported cohort."""

    supported = tuple(item for item in results if _is_supported_record(item))
    unsupported = tuple(item for item in results if not _is_supported_record(item))
    supported_success = sum(item.get("status") == "SUCCESS" for item in supported)
    supported_failure = len(supported) - supported_success
    runtimes = sorted(
        float(item["runtime_ms"])
        for item in supported
        if isinstance(item.get("runtime_ms"), (int, float))
    )
    selections = tuple(
        item
        for item in supported
        if item.get("first_valid_identifier") is not None
        and item.get("selected_identifier") is not None
    )
    changed = sum(item.get("selected_different_from_first_valid") is True for item in selections)
    quality_comparisons = tuple(
        item.get("selected_quality_not_worse_than_first_valid")
        for item in selections
        if item.get("selected_quality_not_worse_than_first_valid") is not None
    )
    failures = Counter(
        str(item.get("failure_family") or "unknown_evidence")
        for item in supported
        if item.get("status") != "SUCCESS"
    )
    return {
        "total_profiles": len(results),
        "supported_attempted": len(supported),
        "supported_success": supported_success,
        "supported_failure": supported_failure,
        "supported_success_rate": (
            round(supported_success / len(supported) * 100.0, 2) if supported else 0.0
        ),
        "unsupported_negative_cohort": len(unsupported),
        "unsupported_success": sum(item.get("status") == "SUCCESS" for item in unsupported),
        "unsupported_failure": sum(item.get("status") != "SUCCESS" for item in unsupported),
        "selection_profiles": len(selections),
        "selection_changed": changed,
        "selection_changed_rate": round(changed / len(selections) * 100.0, 2)
        if selections
        else 0.0,
        "selection_quality_not_worse_count": sum(value is True for value in quality_comparisons),
        "selection_quality_comparison_count": len(quality_comparisons),
        "failure_taxonomy": dict(sorted(failures.items())),
        "performance": {
            "p50_runtime_ms": _percentile(runtimes, 0.50),
            "p95_runtime_ms": _percentile(runtimes, 0.95),
            "median_trace_size_bytes": _median_metric(supported, "trace_size_bytes"),
        },
    }


def failure_family(
    failure_info: Mapping[str, Any] | None,
    result: Any = None,
) -> str | None:
    if failure_info is None and result is None:
        return None
    values: list[str] = []
    if failure_info is not None:
        for key in ("root_cause", "final_error_code", "secondary_causes", "all_errors"):
            value = failure_info.get(key)
            if isinstance(value, str):
                values.append(value)
            elif isinstance(value, (tuple, list, set, frozenset)):
                values.extend(item for item in value if isinstance(item, str))
    if result is not None:
        errors = getattr(result, "errors", ())
        values.extend(item for item in errors if isinstance(item, str))
    joined = " ".join(values).upper()
    if "SEMANTIC_OPENER" in joined:
        return "semantic_opener"
    if "SESSION_EXERCISE_COUNT" in joined or "EXERCISE_COUNT_OUT_OF_RANGE" in joined:
        return "session_count"
    if "REQUIRED_SLOT" in joined or "REQUIRED_PATTERN" in joined:
        return "required_slot"
    if "SAFETY" in joined or "EQUIPMENT" in joined or "NO_SAFE_EXERCISE" in joined:
        return "safety_equipment"
    if "VOLUME" in joined or "PRIORITY_HARD_MINIMUM" in joined:
        return "hard_volume"
    if "RECOVERY" in joined:
        return "recovery"
    if "PRESCRIPTION" in joined or "REP_RANGE" in joined:
        return "prescription"
    if "CATALOG" in joined or "ELIGIBLE_EXERCISES" in joined:
        return "catalog_gap"
    if "UNKNOWN" in joined or "EVIDENCE" in joined:
        return "unknown_evidence"
    return "other" if values else "unknown_evidence"


def unsupported_profile_failure(profile: Any, support: ProfileSupport) -> dict[str, Any]:
    """Return a common, explicit negative-cohort failure record."""

    return {
        "final_error_code": "UNSUPPORTED_RESISTANCE_TRAINING_DAYS",
        "all_errors": list(support.reason_codes),
        "root_cause": "UNSUPPORTED_RESISTANCE_TRAINING_DAYS",
        "secondary_causes": [],
        "rule_file": "app/profile/training_compatibility.py",
        "rule_func": "require_supported_resistance_training_days()",
        "actual_val": (
            f"{profile.experience_level.value} با {profile.training_days_per_week} روز تمرین"
        ),
        "limit_val": "تعداد روزهای مجاز طبق ماتریس سازگاری تمرین مقاومتی",
        "failing_phase": "input_compatibility_validation",
        "exact_description_fa": (
            "ترکیب سطح تجربه و تعداد روزهای تمرین در ماتریس تولید برنامه پشتیبانی نمی‌شود."
        ),
    }


def write_audit_json(results: Sequence[Mapping[str, Any]], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(_json_safe(results), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _trace_for_result(result: Any, program: Any) -> tuple[Mapping[str, Any], ...]:
    program_trace = getattr(program, "decision_trace", ()) if program is not None else ()
    result_trace = getattr(result, "decision_trace", ()) if result is not None else ()
    trace = (
        program_trace
        if isinstance(program_trace, (tuple, list)) and program_trace
        else result_trace
    )
    return tuple(item for item in trace if isinstance(item, Mapping))


def _latest_stage(trace: Sequence[Mapping[str, Any]], stage: str) -> Mapping[str, Any]:
    return next((item for item in reversed(trace) if item.get("stage") == stage), {})


def _quality_from_selection_trace(
    selection_trace: Mapping[str, Any], program: Any
) -> dict[str, Any]:
    quality = selection_trace.get("summarized_quality_key")
    if isinstance(quality, Mapping):
        return dict(_json_safe(quality))
    aggregate = getattr(program, "aggregate_metrics", {}) if program is not None else {}
    coach_quality = aggregate.get("coach_quality", {}) if isinstance(aggregate, Mapping) else {}
    selection_quality = (
        coach_quality.get("selection_quality", {})
        if isinstance(coach_quality, Mapping)
        else {}
    )
    return dict(_json_safe(selection_quality)) if isinstance(selection_quality, Mapping) else {}


def _selected_split_score(program: Any) -> float | int | None:
    score = getattr(getattr(program, "split", None), "score", None)
    return score if isinstance(score, (int, float)) and not isinstance(score, bool) else None


def _critical_quality_floor(quality: Mapping[str, Any]) -> float | None:
    dimensions = quality.get("critical_dimensions")
    if not isinstance(dimensions, Mapping):
        return None
    values = [
        float(value)
        for value in dimensions.values()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    return min(values) if values else None


def _quality_value(quality: Mapping[str, Any], key: str) -> float | int | None:
    value = quality.get(key)
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _trace_size_bytes(trace: Mapping[str, Any]) -> int:
    if not trace:
        return 0
    return len(
        json.dumps(_json_safe(trace), ensure_ascii=False, sort_keys=True).encode("utf-8")
    )


def _is_supported_record(record: Mapping[str, Any]) -> bool:
    return record.get("supported") is True or record.get("cohort") == SUPPORTED_COHORT


def _percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return round(values[0], 3)
    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return round(values[lower] + (values[upper] - values[lower]) * weight, 3)


def _median_metric(results: Sequence[Mapping[str, Any]], key: str) -> float | None:
    values = [
        float(item[key])
        for item in results
        if isinstance(item.get(key), (int, float)) and not isinstance(item.get(key), bool)
    ]
    return round(float(median(values)), 3) if values else None


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return _json_safe(value.value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (UUID, Path)):
        return str(value)
    if is_dataclass(value):
        return _json_safe(asdict(value))  # type: ignore[arg-type]
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [_json_safe(item) for item in value]
        return sorted(items, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True))
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump(mode="json"))
    if hasattr(value, "__dict__"):
        return _json_safe(vars(value))
    return str(value)


def _mapping_or_empty(value: Any) -> dict[str, Any]:
    return dict(_json_safe(value)) if isinstance(value, Mapping) else {}


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _enum_value(value: Any) -> str | None:
    value = value.value if isinstance(value, Enum) else value
    return value if isinstance(value, str) else None


def _integer_or_zero(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return 0
