"""Audit catalog availability without changing Program Engine behavior."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.main  # noqa: F401  # register SQLAlchemy models
from app.config import get_settings
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.session_builder import SlotSpec
from app.workouts.program_engine.slot_compatibility import evaluate_candidate_slot_compatibility
from app.workouts.program_engine.supplemental_policy import is_main_resistance_exercise
from app.workouts.service import WorkoutGenerationService
from scripts.generate_200_profiles_eval import (
    generate_200_stratified_profiles,
    profile_to_request,
)
from scripts.program_engine_audit_support import (
    build_profile_audit_record,
    classify_profile_support,
    summarize_audit_results,
    supported_profile_cohort,
    unsupported_profile_failure,
    write_audit_json,
)

_EQUIPMENT_REJECTION = "EXERCISE_REJECTED_MISSING_EQUIPMENT"
_INJURY_REJECTION_MARKERS = (
    "CAUTION",
    "IMPACT",
    "AXIAL",
    "OVERHEAD",
    "BALANCE",
    "RANGE_OF_MOTION",
)


def audit_required_slot_catalog(
    profile: Any,
    *,
    focus: str,
    day_index: int,
    slot: SlotSpec,
    eligible: Sequence[Any],
    rejected_by_id: Mapping[object, Sequence[str]],
    catalog: Sequence[Any],
) -> dict[str, Any]:
    """Explain whether one required slot is a safe catalog gap or a greedy issue."""

    eligible_candidates = tuple(item for item in eligible if _slot_compatible(item, slot, focus))
    blocked_candidates = tuple(
        (item, tuple(rejected_by_id[item.id]))
        for item in catalog
        if item.id in rejected_by_id and _slot_compatible(item, slot, focus)
    )
    reason_counts = Counter(reason for _, reasons in blocked_candidates for reason in reasons)
    safe_catalog_gap = not eligible_candidates
    return {
        "profile_index": _profile_value(profile, "index"),
        "profile_name": _profile_value(profile, "name"),
        "day_index": day_index,
        "focus": focus,
        "required_patterns": tuple(sorted(pattern.value for pattern in slot.patterns)),
        "required_target_muscle": (
            slot.target_muscle.value if slot.target_muscle is not None else None
        ),
        "candidate_pool_at_session_start": len(eligible_candidates),
        "safe_catalog_gap": safe_catalog_gap,
        "greedy_dead_end_proven": False if safe_catalog_gap else None,
        "consumed_by_greedy_choice": 0 if safe_catalog_gap else None,
        "semantic_blocked_by_greedy_choice": 0 if safe_catalog_gap else None,
        "hard_volume_blocked": False if safe_catalog_gap else None,
        "duration_maximum_blocked": False if safe_catalog_gap else None,
        "recovery_blocked": False if safe_catalog_gap else None,
        "alternative_ordering_possible": False if safe_catalog_gap else None,
        "equipment_blocked_candidate_count": sum(
            _has_reason(reasons, _EQUIPMENT_REJECTION) for _, reasons in blocked_candidates
        ),
        "injury_blocked_candidate_count": sum(
            _has_any_reason(reasons, _INJURY_REJECTION_MARKERS) for _, reasons in blocked_candidates
        ),
        "other_eligibility_blocked_candidate_count": sum(
            not _has_reason(reasons, _EQUIPMENT_REJECTION)
            and not _has_any_reason(reasons, _INJURY_REJECTION_MARKERS)
            for _, reasons in blocked_candidates
        ),
        "blocked_reason_counts": dict(sorted(reason_counts.items())),
        "eligible_slot_candidates": tuple(_candidate_summary(item) for item in eligible_candidates),
        "blocked_slot_candidates": tuple(
            {
                **_candidate_summary(item),
                "rejection_reasons": reasons,
            }
            for item, reasons in blocked_candidates
        ),
        "diagnosis": "safe_catalog_gap" if safe_catalog_gap else "requires_construction_trace",
    }


def _slot_compatible(item: Any, slot: SlotSpec, focus: str) -> bool:
    if not is_main_resistance_exercise(item):
        return False
    compatibility = evaluate_candidate_slot_compatibility(
        item,
        allowed_patterns=slot.patterns,
        target_muscles=(
            frozenset({slot.target_muscle}) if slot.target_muscle is not None else None
        ),
        day_focus=focus,
        allow_full_body=focus.startswith("full_body"),
    )
    return bool(compatibility.compatible)


def _candidate_summary(item: Any) -> dict[str, Any]:
    return {
        "id": str(_profile_value(item, "id")),
        "slug": _profile_value(item, "slug"),
        "name": _profile_value(item, "name"),
        "movement_pattern": _enum_value(_profile_value(item, "movement_pattern")),
        "primary_muscle": _enum_value(_profile_value(item, "primary_muscle")),
        "equipment": tuple(
            sorted(_enum_value(value) for value in (_profile_value(item, "equipment", ()) or ()))
        ),
    }


def _profile_value(value: Any, field: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(field, default)
    return getattr(value, field, default)


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _has_reason(reasons: Sequence[str], target: str) -> int:
    return int(target in reasons)


def _has_any_reason(reasons: Sequence[str], markers: Sequence[str]) -> int:
    return int(any(any(marker in reason for marker in markers) for reason in reasons))


def audit_supported_catalog(
    profiles: Sequence[Any],
    *,
    eligible_count_for_profile: Callable[[Any], int],
) -> list[dict[str, Any]]:
    """Return one auditable record per profile, separating support from catalog gaps."""

    records: list[dict[str, Any]] = []
    for profile in profiles:
        support = classify_profile_support(profile)
        if not support.supported:
            record = build_profile_audit_record(
                profile,
                support,
                status="FAILED",
                failure_info=unsupported_profile_failure(profile, support),
            )
            record.update({"catalog_gap": False, "catalog_eligible_count": 0})
            records.append(record)
            continue

        eligible_count = max(0, int(eligible_count_for_profile(profile)))
        catalog_gap = eligible_count == 0
        failure_info = (
            {
                "final_error_code": "CATALOG_GAP",
                "all_errors": ["NO_ELIGIBLE_EXERCISES"],
                "root_cause": "CATALOG_GAP",
                "secondary_causes": [],
                "failing_phase": "catalog_eligibility_audit",
            }
            if catalog_gap
            else None
        )
        record = build_profile_audit_record(
            profile,
            support,
            status="FAILED" if catalog_gap else "SUCCESS",
            failure_info=failure_info,
        )
        record.update(
            {
                "catalog_gap": catalog_gap,
                "catalog_eligible_count": eligible_count,
            }
        )
        records.append(record)
    return records


def _load_catalog() -> tuple[Any, ...]:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        service = WorkoutGenerationService(session, settings=None)
        return tuple(service._load_catalog())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260901)
    parser.add_argument("--output", default=None, help="Optional JSON output path")
    args = parser.parse_args()

    profiles = supported_profile_cohort(
        generate_200_stratified_profiles,
        count=args.count,
        seed=args.seed,
    )
    catalog = _load_catalog()

    def eligible_count(profile: Any) -> int:
        request = profile_to_request(profile, UUID(int=profile.index))
        normalized = normalize_request(request, RULESET)
        return len(filter_eligible_exercises(normalized, catalog).eligible)

    records = audit_supported_catalog(profiles, eligible_count_for_profile=eligible_count)
    summary = summarize_audit_results(records)
    if args.output:
        write_audit_json(records, args.output)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
