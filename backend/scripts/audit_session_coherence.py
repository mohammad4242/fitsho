"""Run the diverse-profile audit and preserve engine session-coherence evidence.

This is deliberately a small companion to ``run_20_profiles_debug``.  That script
renders a human-facing PDF but does not retain the ``session_coherence`` metrics
already attached to successful programs.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from importlib import import_module
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.training_templates.engine_reference import load_template_references
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.service import WorkoutGenerationService, WorkoutGenerationSettings

_run20 = import_module(
    "scripts.run_20_profiles_debug" if __package__ else "run_20_profiles_debug"
)
analyze_failure = _run20.analyze_failure
define_20_diverse_profiles = _run20.define_20_diverse_profiles
profile_to_request = _run20.profile_to_request


def _json_ready(value: object) -> object:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, dict):
        return {str(_json_ready(key)): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_json_ready(item) for item in value]
    return str(value)


def summarize_coherence(results: list[dict[str, Any]]) -> dict[str, int]:
    """Aggregate persisted coherence metrics using the engine's canonical keys."""
    successful = [item for item in results if item.get("status") == "SUCCESS"]
    coherence = [item.get("session_coherence", {}) for item in successful]
    return {
        "profiles_requested": len(results),
        "profiles_executed": len(results),
        "successes": len(successful),
        "failures": len(results) - len(successful),
        "coherence_metrics_present": sum(bool(item) for item in coherence),
        "orphan_direct_exposure_count": sum(
            int(item.get("orphan_direct_exposure_count", 0)) for item in coherence
        ),
        "post_construction_out_of_scope_direct_additions": sum(
            int(item.get("post_construction_out_of_scope_direct_muscle_additions", 0))
            for item in coherence
        ),
    }


def run_audit(output_path: Path, *, limit: int | None = None) -> dict[str, Any]:
    """Generate the 20 profiles and retain session-level aggregate metrics."""
    settings = get_settings()
    profiles = define_20_diverse_profiles()
    if limit is not None:
        profiles = profiles[:limit]

    results: list[dict[str, Any]] = []
    with Session(create_engine(settings.database_url)) as db:
        service = WorkoutGenerationService(
            db,
            settings=WorkoutGenerationSettings(
                provider_name="fitsho_domain",
                model_id="program_engine_v1",
                prompt_version="audit",
                generation_policy_version="resistance_training_v1",
                catalog_programming_version="v1",
                max_repair_attempts=0,
                cooldown_seconds=0,
                max_candidates=80,
                max_request_bytes=262144,
                warmup_minutes=5,
            ),
        )
        catalog = service._load_catalog()
        references = load_template_references(db)
        for profile in profiles:
            request = profile_to_request(profile, uuid4())
            try:
                result = generate_program(
                    request,
                    catalog,
                    RULESET,
                    reference_templates=references,
                )
            except Exception as exc:  # Preserve the actual failure in the report.
                results.append(
                    {
                        "profile_index": profile.index,
                        "status": "FAILED",
                        "exception": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue

            if result.is_success and result.program is not None:
                metrics = result.program.aggregate_metrics
                results.append(
                    {
                        "profile_index": profile.index,
                        "status": "SUCCESS",
                        "days_count": len(result.program.weekly_schedule),
                        "target_days": profile.training_days_per_week,
                        "target_duration_minutes": profile.session_duration_minutes,
                        "split": result.program.split.split_type.value,
                        "session_coherence": metrics.get("session_coherence", {}),
                        "weekly_coverage": metrics.get("weekly_coverage", {}),
                        "final_quality_gate": metrics.get("final_quality_gate", {}),
                    }
                )
            else:
                results.append(
                    {
                        "profile_index": profile.index,
                        "status": "FAILED",
                        "failure": analyze_failure(result, request),
                    }
                )

    summary = summarize_coherence(results)
    summary["profiles_requested"] = len(profiles)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "source_harness": "scripts.run_20_profiles_debug.define_20_diverse_profiles",
        "summary": summary,
        "results": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(_json_ready(payload), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit aggregate session-coherence metrics.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("var/reports/session_coherence_audit.json"),
    )
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N profiles.")
    args = parser.parse_args()
    payload = run_audit(args.output.resolve(), limit=args.limit)
    print(json.dumps({"output": str(args.output.resolve()), **payload["summary"]}))


if __name__ == "__main__":
    main()
