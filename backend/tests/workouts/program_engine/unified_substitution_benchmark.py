"""Backward-compatible home-equipment benchmark for substitution closeout."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.exercises.enums import Equipment, MuscleGroup
from app.workouts.program_engine.eligibility import filter_eligible_exercises
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.equipment import effective_required_equipment
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from tests.workouts.program_engine.golden_fixtures import full_catalog, request

_SUPPLEMENTAL_MUSCLES = frozenset(
    {
        MuscleGroup.FOREARMS,
        MuscleGroup.ABS,
        MuscleGroup.OBLIQUES,
        MuscleGroup.LOWER_BACK,
        MuscleGroup.NECK,
    }
)


@dataclass(frozen=True)
class HomeCase:
    name: str
    equipment: tuple[Equipment, ...]
    experience: str
    goal: str
    days: int


HOME_CASES = (
    HomeCase("bodyweight", (Equipment.BODYWEIGHT,), "beginner", "strength", 2),
    HomeCase("dumbbells", (Equipment.DUMBBELL,), "intermediate", "muscle_gain", 4),
    HomeCase(
        "bodyweight_dumbbells",
        (Equipment.BODYWEIGHT, Equipment.DUMBBELL),
        "beginner",
        "muscle_gain",
        3,
    ),
    HomeCase(
        "dumbbells_bench",
        (Equipment.DUMBBELL, Equipment.BENCH),
        "intermediate",
        "strength",
        4,
    ),
    HomeCase("bands", (Equipment.RESISTANCE_BAND,), "beginner", "strength", 3),
    HomeCase(
        "bands_dumbbells",
        (Equipment.RESISTANCE_BAND, Equipment.DUMBBELL),
        "intermediate",
        "muscle_gain",
        2,
    ),
    HomeCase(
        "bodyweight_pull_up_bar",
        (Equipment.BODYWEIGHT, Equipment.PULL_UP_BAR),
        "intermediate",
        "strength",
        4,
    ),
    HomeCase(
        "complete_home",
        (
            Equipment.DUMBBELL,
            Equipment.BENCH,
            Equipment.RESISTANCE_BAND,
            Equipment.PULL_UP_BAR,
        ),
        "beginner",
        "muscle_gain",
        3,
    ),
)


def run_benchmark() -> dict[str, object]:
    catalog = tuple(full_catalog())
    by_id = {candidate.id: candidate for candidate in catalog}
    totals = {
        "profiles": len(HOME_CASES),
        "generation_successes": 0,
        "unsat": 0,
        "substitution_requests": 0,
        "substitution_successes": 0,
        "exact_role_successes": 0,
        "focus_measured": 0,
        "focus_preserved": 0,
        "movement_family_fallbacks": 0,
        "equipment_violations": 0,
        "safety_violations": 0,
        "deterministic_profiles": 0,
    }
    engine_request_count = 0
    engine_metrics_available = True
    profiles: list[dict[str, object]] = []
    for case in HOME_CASES:
        source = request(
            available_equipment=list(case.equipment),
            training_experience=case.experience,
            training_age_months=36 if case.experience == "intermediate" else 3,
            primary_goal=case.goal,
            available_training_days=case.days,
        )
        first = generate_program(source, catalog, RULESET)
        second = generate_program(source, catalog, RULESET)
        deterministic = first == second
        totals["deterministic_profiles"] += int(deterministic)
        record: dict[str, object] = {
            "name": case.name,
            "equipment": tuple(item.value for item in case.equipment),
            "days": case.days,
            "goal": case.goal,
            "success": first.program is not None,
            "deterministic": deterministic,
            "errors": first.errors,
        }
        if first.program is None:
            totals["unsat"] += 1
            profiles.append(record)
            continue
        totals["generation_successes"] += 1
        engine_count = first.program.aggregate_metrics.get("substitution_requests")
        if isinstance(engine_count, int):
            engine_request_count += engine_count
        else:
            engine_metrics_available = False
        normalized = normalize_request(source)
        profile_metrics = _program_metrics(first.program, normalized, by_id)
        for key, value in profile_metrics.items():
            totals[key] += value
        record.update(profile_metrics)
        profiles.append(record)

    successes = totals["generation_successes"]
    substitution_successes = totals["substitution_successes"]
    focus_measured = totals["focus_measured"]
    aggregate: dict[str, object] = {
        **totals,
        "generation_success_rate": _rate(successes, totals["profiles"]),
        "substitution_success_rate": _rate(substitution_successes, totals["substitution_requests"]),
        "exact_role_rate": _rate(totals["exact_role_successes"], substitution_successes),
        "muscle_focus_preservation_rate": (
            _rate(totals["focus_preserved"], focus_measured) if focus_measured else None
        ),
        "movement_family_fallback_rate": _rate(
            totals["movement_family_fallbacks"], substitution_successes
        ),
        "determinism_rate": _rate(totals["deterministic_profiles"], totals["profiles"]),
        "engine_substitution_request_count": (
            engine_request_count if engine_metrics_available else None
        ),
    }
    return {"aggregate": aggregate, "home_subgroups": profiles}


def _program_metrics(
    program: Any,
    normalized: Any,
    by_id: dict[object, Any],
) -> dict[str, int]:
    metrics = {
        "substitution_requests": 0,
        "substitution_successes": 0,
        "exact_role_successes": 0,
        "focus_measured": 0,
        "focus_preserved": 0,
        "movement_family_fallbacks": 0,
        "equipment_violations": 0,
        "safety_violations": 0,
    }
    available = normalized.constraints.available_equipment
    for day in program.weekly_schedule:
        for programmed in day.exercises:
            target = by_id.get(programmed.exercise_id)
            metrics["equipment_violations"] += _equipment_violation(programmed, available)
            if target is not None:
                metrics["safety_violations"] += _safety_violation(target, normalized)
            if programmed.primary_muscle in _SUPPLEMENTAL_MUSCLES or target is None:
                continue
            metrics["substitution_requests"] += 1
            alternatives = tuple(
                by_id[item_id]
                for item_id in programmed.substitution_exercise_ids
                if item_id in by_id
            )
            for alternative in alternatives:
                metrics["equipment_violations"] += _equipment_violation(alternative, available)
                metrics["safety_violations"] += _safety_violation(alternative, normalized)
            if not alternatives:
                continue
            metrics["substitution_successes"] += 1
            first = alternatives[0]
            target_focus = getattr(target, "muscle_focus", None)
            first_focus = getattr(first, "muscle_focus", None)
            common_exact = (
                first.movement_pattern is target.movement_pattern
                and first.primary_muscle is target.primary_muscle
                and first.exercise_type is target.exercise_type
            )
            if target_focus is not None and first_focus is not None:
                metrics["focus_measured"] += 1
                metrics["focus_preserved"] += int(first_focus is target_focus)
                common_exact = common_exact and first_focus is target_focus
            metrics["exact_role_successes"] += int(common_exact)
            metrics["movement_family_fallbacks"] += int(
                first.movement_pattern is not target.movement_pattern
            )
    return metrics


def _equipment_violation(candidate: Any, available: frozenset[Equipment]) -> int:
    required = effective_required_equipment(candidate.equipment, candidate.movement_pattern)
    return int(not required.issubset(available))


def _safety_violation(candidate: Any, normalized: Any) -> int:
    eligibility = filter_eligible_exercises(normalized, (candidate,))
    if eligibility.eligible:
        return 0
    reasons = {
        reason
        for rejected in eligibility.rejected
        for reason in rejected.reason_codes
        if reason != "EXERCISE_REJECTED_MISSING_EQUIPMENT"
    }
    return int(bool(reasons))


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = run_benchmark()
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(json.dumps(payload["aggregate"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
