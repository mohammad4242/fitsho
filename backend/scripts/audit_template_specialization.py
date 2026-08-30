from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_engine
from app.exercises.enums import MuscleGroup
from app.training_templates.engine_reference import load_template_references
from app.training_templates.tags import TemplateFocusTag
from scripts.audit_template_survival import (
    DURATIONS,
    LEVELS,
    DiagnosticRecorder,
    _baseline_request,
    _competition_case,
    _forced_case,
    _json_ready,
    _load_catalog,
)

_PRIORITY_BY_TAG: dict[TemplateFocusTag, frozenset[MuscleGroup]] = {
    TemplateFocusTag.ARMS_PRIORITY: frozenset({MuscleGroup.BICEPS, MuscleGroup.TRICEPS}),
    TemplateFocusTag.CHEST_PRIORITY: frozenset({MuscleGroup.CHEST}),
    TemplateFocusTag.BACK_PRIORITY: frozenset({MuscleGroup.BACK}),
    TemplateFocusTag.SHOULDERS_PRIORITY: frozenset({MuscleGroup.SHOULDERS}),
    TemplateFocusTag.GLUTE_PRIORITY: frozenset({MuscleGroup.GLUTES}),
    TemplateFocusTag.QUAD_PRIORITY: frozenset({MuscleGroup.QUADRICEPS}),
    TemplateFocusTag.HAMSTRINGS_PRIORITY: frozenset({MuscleGroup.HAMSTRINGS}),
    TemplateFocusTag.LOWER_PRIORITY: frozenset(
        {MuscleGroup.QUADRICEPS, MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES}
    ),
}


def priority_muscles_for_tags(
    tags: Iterable[TemplateFocusTag],
) -> frozenset[MuscleGroup]:
    semantic_tags = frozenset(tags)
    if TemplateFocusTag.SPECIALIZATION not in semantic_tags:
        return frozenset()
    return frozenset(
        muscle
        for tag in semantic_tags
        for muscle in _PRIORITY_BY_TAG.get(tag, frozenset())
    )


def run_specialization_audit(output_path: Path) -> dict[str, object]:
    settings = get_settings()
    with Session(get_engine(settings.database_url)) as db:
        references = tuple(load_template_references(db))
        specialization = tuple(
            reference
            for reference in references
            if TemplateFocusTag.SPECIALIZATION in reference.focus_tags
            and priority_muscles_for_tags(reference.focus_tags)
            and any(level in LEVELS for level in reference.supported_levels)
        )
        catalog = _load_catalog(db)
        forced_cases: list[dict[str, object]] = []
        competition_cases: list[dict[str, object]] = []
        with DiagnosticRecorder() as recorder:
            for reference in specialization:
                priorities = priority_muscles_for_tags(reference.focus_tags)
                for level in reference.supported_levels:
                    if level not in LEVELS:
                        continue
                    scenario_templates = tuple(
                        item
                        for item in references
                        if item.days_per_week == reference.days_per_week
                        and level in item.supported_levels
                    )
                    for duration in DURATIONS:
                        baseline = _baseline_request(
                            level, reference.days_per_week, duration
                        )
                        request = baseline.model_copy(update={"priority_muscles": priorities})
                        forced = _forced_case(recorder, reference, request, catalog)
                        forced["priority_muscles"] = tuple(
                            sorted(muscle.value for muscle in priorities)
                        )
                        forced_cases.append(forced)
                        competition = _competition_case(
                            recorder, scenario_templates, request, catalog
                        )
                        competition["intended_specialization_template"] = reference.slug
                        competition["priority_muscles"] = tuple(
                            sorted(muscle.value for muscle in priorities)
                        )
                        competition_cases.append(competition)
        passed = sum(case["forced_template_result"] == "PASS" for case in forced_cases)
        selected = sum(
            case["final_selected_template"] == case["intended_specialization_template"]
            for case in competition_cases
        )
        payload = {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "ruleset_version": "resistance_training_v5",
            "specialization_template_count": len(specialization),
            "forced_cases": forced_cases,
            "competition_cases": competition_cases,
            "summary": {
                "forced_tests": len(forced_cases),
                "forced_passed": passed,
                "forced_failed": len(forced_cases) - passed,
                "forced_success_rate": round(100 * passed / len(forced_cases), 1)
                if forced_cases
                else 0.0,
                "competition_tests": len(competition_cases),
                "intended_specialization_selected": selected,
            },
        }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(_json_ready(payload), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return payload


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit priority-matched specialization templates.")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    result = run_specialization_audit(args.output.resolve())
    summary = cast(dict[str, object], result["summary"])
    print(json.dumps({"output": str(args.output.resolve()), **summary}))
