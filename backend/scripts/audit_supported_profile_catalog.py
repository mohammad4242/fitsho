"""Audit catalog availability without changing Program Engine behavior."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
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
