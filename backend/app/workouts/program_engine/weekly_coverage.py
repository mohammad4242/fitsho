from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.exercises.enums import MovementPattern, MuscleGroup
from app.workouts.program_engine.coverage_evidence import candidate_availability_evidence
from app.workouts.program_engine.effective_volume import calculate_effective_volume
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import ExerciseCandidate, WorkoutDay
from app.workouts.program_engine.substitution_policy import (
    FULL_BODY_PATTERN_GROUPS,
    HINGE_PATTERNS,
    KNEE_PATTERNS,
    PULL_PATTERNS,
    PUSH_PATTERNS,
    SHOULDER_PATTERNS,
)

_MAJOR_MUSCLES = tuple(
    MuscleGroup(value)
    for value in ("chest", "back", "shoulders", "quadriceps", "hamstrings", "glutes")
)
_MUSCLE_PATTERNS: dict[str, frozenset[MovementPattern]] = {
    "chest": PUSH_PATTERNS,
    "back": PULL_PATTERNS,
    "shoulders": PUSH_PATTERNS | PULL_PATTERNS | SHOULDER_PATTERNS,
    "quadriceps": KNEE_PATTERNS,
    "hamstrings": KNEE_PATTERNS | HINGE_PATTERNS,
    "glutes": KNEE_PATTERNS | HINGE_PATTERNS,
}


@dataclass(frozen=True)
class WeeklyCoverage:
    metrics: dict[str, object]


def build_coverage_availability_evidence(
    eligible: Iterable[ExerciseCandidate],
    rejected: Iterable[tuple[ExerciseCandidate, tuple[str, ...]]],
) -> dict[str, object]:
    """Build deterministic candidate evidence for required patterns and muscles."""
    records = tuple(
        sorted(((candidate, None) for candidate in eligible), key=lambda item: str(item[0].id))
    ) + tuple(sorted(rejected, key=lambda item: str(item[0].id)))
    return {
        "patterns": {
            name: candidate_availability_evidence(
                (candidate, reasons)
                for candidate, reasons in records
                if candidate.movement_pattern in patterns
            )
            for name, patterns in FULL_BODY_PATTERN_GROUPS
        },
        "muscles": {
            muscle.value: candidate_availability_evidence(
                (candidate, reasons)
                for candidate, reasons in records
                if _candidate_targets_muscle(candidate, muscle.value)
            )
            for muscle in _MAJOR_MUSCLES
        },
    }


def assess_weekly_coverage(
    days: tuple[WorkoutDay, ...],
    aggregate_metrics: Mapping[str, object] | None = None,
    *,
    ruleset: ProgramRuleset,
    availability_evidence: Mapping[str, object] | None = None,
    full_body_claim: bool | None = None,
) -> WeeklyCoverage:
    """Assess final exercises without inferring coverage from template regions."""
    evidence = availability_evidence
    if evidence is None and aggregate_metrics is not None:
        value = aggregate_metrics.get("coverage_availability_evidence")
        evidence = value if isinstance(value, Mapping) else None
    claimed = (
        full_body_claim
        if full_body_claim is not None
        else any(day.focus.startswith("full_body") for day in days)
    )
    if not claimed:
        return WeeklyCoverage(_metrics("not_applicable", availability_evidence=evidence))

    items = tuple(item for day in days for item in day.exercises)
    effective = calculate_effective_volume(items, ruleset)
    covered_muscles = tuple(
        muscle.value
        for muscle in _MAJOR_MUSCLES
        if effective.effective_sets_by_muscle.get(muscle.value, 0) > 0
    )
    missing_muscles = tuple(
        muscle.value for muscle in _MAJOR_MUSCLES if muscle.value not in covered_muscles
    )
    muscle_evidence = _nested_mapping(evidence, "muscles")
    unavailable_muscles = {
        muscle
        for muscle in missing_muscles
        if _evidence_is_unavailable(muscle_evidence.get(muscle))
    }
    actual_patterns = {item.movement_pattern for item in items}
    covered_patterns = tuple(
        name
        for name, patterns in FULL_BODY_PATTERN_GROUPS
        if actual_patterns.intersection(patterns)
    )
    missing_patterns = tuple(
        name
        for name, patterns in FULL_BODY_PATTERN_GROUPS
        if not actual_patterns.intersection(patterns)
    )
    pattern_evidence = _nested_mapping(evidence, "patterns")
    unavailable_patterns = tuple(
        name for name in missing_patterns if _evidence_is_unavailable(pattern_evidence.get(name))
    )

    missing_muscle_set = set(missing_muscles)
    all_missing_unavailable = bool(missing_muscle_set or missing_patterns) and (
        missing_muscle_set.issubset(unavailable_muscles)
        and set(missing_patterns).issubset(unavailable_patterns)
    )
    status = (
        "satisfied"
        if not missing_muscles and not missing_patterns
        else "constrained"
        if all_missing_unavailable
        else "unsatisfied"
    )
    reasons = [
        *(f"FULL_BODY_COVERAGE_UNAVAILABLE:{muscle}" for muscle in sorted(unavailable_muscles)),
        *(f"FULL_BODY_PATTERN_UNAVAILABLE:{pattern}" for pattern in unavailable_patterns),
        *(
            f"FULL_BODY_COVERAGE_MISSING:{muscle}"
            for muscle in missing_muscles
            if muscle not in unavailable_muscles
        ),
        *(
            f"FULL_BODY_PATTERN_MISSING:{pattern}"
            for pattern in missing_patterns
            if pattern not in unavailable_patterns
        ),
    ]
    if status == "constrained":
        reasons.append("FULL_BODY_COVERAGE_CONSTRAINED")
    return WeeklyCoverage(
        _metrics(
            status,
            covered_patterns=covered_patterns,
            missing_patterns=missing_patterns,
            unavailable_patterns=unavailable_patterns,
            covered_muscles=covered_muscles,
            missing_muscles=missing_muscles,
            unavailable_muscles=tuple(sorted(unavailable_muscles)),
            reason_codes=tuple(dict.fromkeys(reasons)),
            availability_evidence=evidence,
        )
    )


def _metrics(
    status: str,
    *,
    covered_patterns: tuple[str, ...] = (),
    missing_patterns: tuple[str, ...] = (),
    unavailable_patterns: tuple[str, ...] = (),
    covered_muscles: tuple[str, ...] = (),
    missing_muscles: tuple[str, ...] = (),
    unavailable_muscles: tuple[str, ...] = (),
    reason_codes: tuple[str, ...] = (),
    availability_evidence: Mapping[str, object] | None = None,
) -> dict[str, object]:
    return {
        "status": status,
        "claimed_full_body": status != "not_applicable",
        "claimed_balanced": status == "satisfied",
        "fully_balanced": status == "satisfied",
        "required_patterns": tuple(name for name, _patterns in FULL_BODY_PATTERN_GROUPS),
        "covered_patterns": covered_patterns,
        "missing_patterns": missing_patterns,
        "unavailable_patterns": unavailable_patterns,
        "major_muscles": tuple(muscle.value for muscle in _MAJOR_MUSCLES),
        "covered_major_muscles": covered_muscles,
        "missing_major_muscles": missing_muscles,
        "unavailable_major_muscles": unavailable_muscles,
        "reason_codes": reason_codes,
        "constraint_reason_codes": reason_codes,
        "availability_evidence": availability_evidence or {"patterns": {}, "muscles": {}},
    }


def _candidate_targets_muscle(candidate: ExerciseCandidate, muscle: str) -> bool:
    return candidate.movement_pattern in _MUSCLE_PATTERNS[muscle] and (
        candidate.primary_muscle is not None
        and candidate.primary_muscle.value == muscle
        or any(item.value == muscle for item in candidate.secondary_muscles)
    )


def _nested_mapping(value: Mapping[str, object] | None, key: str) -> Mapping[str, object]:
    nested = value.get(key) if value is not None else None
    return nested if isinstance(nested, Mapping) else {}


def _evidence_is_unavailable(value: object) -> bool:
    return isinstance(value, Mapping) and value.get("unavailable") is True


__all__ = ["WeeklyCoverage", "assess_weekly_coverage", "build_coverage_availability_evidence"]
