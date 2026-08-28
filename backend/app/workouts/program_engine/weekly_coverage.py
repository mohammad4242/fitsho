from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.exercises.enums import MovementPattern, MuscleGroup
from app.workouts.program_engine.effective_volume import calculate_effective_volume
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import ExerciseCandidate, WorkoutDay
from app.workouts.program_engine.substitution_policy import (
    FULL_BODY_PATTERN_GROUPS,
    HINGE_PATTERNS,
    KNEE_PATTERNS,
    PULL_PATTERNS,
    PUSH_PATTERNS,
)

_MAJOR_MUSCLES: tuple[MuscleGroup, ...] = (
    MuscleGroup.CHEST,
    MuscleGroup.BACK,
    MuscleGroup.SHOULDERS,
    MuscleGroup.QUADRICEPS,
    MuscleGroup.HAMSTRINGS,
    MuscleGroup.GLUTES,
)

_MUSCLE_PATTERNS: dict[str, frozenset[MovementPattern]] = {
    "chest": PUSH_PATTERNS,
    "back": PULL_PATTERNS,
    "shoulders": PUSH_PATTERNS | PULL_PATTERNS,
    "quadriceps": KNEE_PATTERNS,
    "hamstrings": KNEE_PATTERNS | HINGE_PATTERNS,
    "glutes": KNEE_PATTERNS | HINGE_PATTERNS,
}

_AVAILABILITY_REJECTION_REASONS = frozenset(
    {
        "EXERCISE_REJECTED_INACTIVE",
        "EXERCISE_REJECTED_NOT_PROGRAMMABLE",
        "EXERCISE_REJECTED_NEEDS_REVIEW",
        "EXERCISE_REJECTED_MISSING_METADATA",
        "EXERCISE_REJECTED_NOT_RESISTANCE_TRAINING",
        "EXERCISE_REJECTED_MISSING_EQUIPMENT",
        "EXERCISE_REJECTED_SKILL_TOO_HIGH",
        "EXERCISE_REJECTED_BLOCKED_CAUTION_TAG",
        "EXERCISE_REJECTED_IMPACT_LIMIT",
        "EXERCISE_REJECTED_AXIAL_LOAD_LIMIT",
        "EXERCISE_REJECTED_BALANCE_DEMAND",
        "EXERCISE_REJECTED_OVERHEAD_LIMIT",
        "EXERCISE_REJECTED_RANGE_OF_MOTION",
    }
)


@dataclass(frozen=True)
class WeeklyCoverage:
    metrics: dict[str, object]


def build_coverage_availability_evidence(
    eligible: Iterable[ExerciseCandidate],
    rejected: Iterable[tuple[ExerciseCandidate, tuple[str, ...]]],
) -> dict[str, object]:
    """Build candidate-level evidence for each required pattern and major muscle."""

    records = tuple(
        sorted(
            ((candidate, None) for candidate in eligible),
            key=lambda item: str(item[0].id),
        )
    ) + tuple(
        sorted(
            ((candidate, reasons) for candidate, reasons in rejected),
            key=lambda item: str(item[0].id),
        )
    )
    return {
        "patterns": {
            name: _candidate_evidence(
                (candidate, reasons)
                for candidate, reasons in records
                if candidate.movement_pattern in patterns
            )
            for name, patterns in FULL_BODY_PATTERN_GROUPS
        },
        "muscles": {
            muscle: _candidate_evidence(
                (candidate, reasons)
                for candidate, reasons in records
                if _candidate_targets_muscle(candidate, muscle)
            )
            for muscle in (item.value for item in _MAJOR_MUSCLES)
        },
    }


def assess_weekly_coverage(
    days: tuple[WorkoutDay, ...],
    aggregate_metrics: Mapping[str, object] | None = None,
    *,
    ruleset: ProgramRuleset,
    availability_evidence: Mapping[str, object] | None = None,
) -> WeeklyCoverage:
    """Assess actual full-body coverage and preserve explicit unavailable causes."""

    evidence = availability_evidence
    if evidence is None and aggregate_metrics is not None:
        value = aggregate_metrics.get("coverage_availability_evidence")
        evidence = value if isinstance(value, Mapping) else None
    if not _is_full_body_claim(days):
        return WeeklyCoverage(_metrics("not_applicable", availability_evidence=evidence))

    effective = calculate_effective_volume(
        (item for day in days for item in day.exercises),
        ruleset,
    )
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

    covered_patterns: list[str] = []
    missing_patterns: list[str] = []
    unavailable_patterns: list[str] = []
    pattern_evidence = _nested_mapping(evidence, "patterns")
    for name, patterns in FULL_BODY_PATTERN_GROUPS:
        if any(item.movement_pattern in patterns for day in days for item in day.exercises):
            covered_patterns.append(name)
            continue
        missing_patterns.append(name)
        if _evidence_is_unavailable(pattern_evidence.get(name)):
            unavailable_patterns.append(name)

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
            covered_patterns=tuple(covered_patterns),
            missing_patterns=tuple(missing_patterns),
            unavailable_patterns=tuple(unavailable_patterns),
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
    claimed = status != "not_applicable"
    return {
        "status": status,
        "claimed_full_body": claimed,
        "claimed_balanced": status == "satisfied",
        "fully_balanced": status == "satisfied",
        "required_patterns": tuple(name for name, _patterns in FULL_BODY_PATTERN_GROUPS),
        "covered_patterns": covered_patterns,
        "missing_patterns": tuple(missing_patterns),
        "unavailable_patterns": tuple(unavailable_patterns),
        "major_muscles": tuple(muscle.value for muscle in _MAJOR_MUSCLES),
        "covered_major_muscles": covered_muscles,
        "missing_major_muscles": tuple(missing_muscles),
        "unavailable_major_muscles": tuple(unavailable_muscles),
        "reason_codes": reason_codes,
        "constraint_reason_codes": reason_codes,
        "availability_evidence": availability_evidence or {"patterns": {}, "muscles": {}},
    }


def _is_full_body_claim(days: tuple[WorkoutDay, ...]) -> bool:
    if any(day.focus.startswith("full_body") for day in days):
        return True
    template_days = tuple(
        day
        for day in days
        if day.focus.startswith("template_reference")
        and day.template_structure_focus == "full_body"
    )
    if not template_days:
        return False
    upper = {
        MuscleGroup.CHEST,
        MuscleGroup.BACK,
        MuscleGroup.SHOULDERS,
        MuscleGroup.BICEPS,
        MuscleGroup.TRICEPS,
    }
    lower = {
        MuscleGroup.QUADRICEPS,
        MuscleGroup.HAMSTRINGS,
        MuscleGroup.GLUTES,
        MuscleGroup.CALVES,
    }
    targets = {muscle for day in template_days for muscle in day.template_target_muscles}
    return bool(targets.intersection(upper) and targets.intersection(lower))


def _candidate_evidence(
    records: Iterable[tuple[ExerciseCandidate, tuple[str, ...] | None]],
) -> dict[str, object]:
    entries = tuple(records)
    eligible = tuple(candidate for candidate, reasons in entries if reasons is None)
    rejected = tuple((candidate, reasons) for candidate, reasons in entries if reasons is not None)
    rejection_reason_codes = tuple(
        sorted({reason for _candidate, reasons in rejected for reason in reasons})
    )
    unavailable = not eligible and (
        not rejected
        or all(
            set(reasons).intersection(_AVAILABILITY_REJECTION_REASONS)
            for _candidate, reasons in rejected
        )
    )
    return {
        "candidate_count": len(entries),
        "eligible_candidate_count": len(eligible),
        "rejected_candidate_count": len(rejected),
        "eligible_candidate_ids": tuple(str(candidate.id) for candidate in eligible),
        "rejected_candidates": tuple(
            {
                "exercise_id": str(candidate.id),
                "reason_codes": reasons,
            }
            for candidate, reasons in rejected
        ),
        "rejection_reason_codes": rejection_reason_codes,
        "availability_reason_codes": (
            ("COVERAGE_CATALOG_NO_COMPATIBLE_CANDIDATE",)
            if not entries
            else tuple(
                sorted(
                    {
                        reason
                        for _candidate, reasons in rejected
                        for reason in reasons
                        if reason in _AVAILABILITY_REJECTION_REASONS
                    }
                )
            )
        ),
        "unavailable": unavailable,
    }


def _candidate_targets_muscle(candidate: ExerciseCandidate, muscle: str) -> bool:
    if candidate.movement_pattern not in _MUSCLE_PATTERNS[muscle]:
        return False
    return (
        candidate.primary_muscle is not None and candidate.primary_muscle.value == muscle
    ) or any(item.value == muscle for item in candidate.secondary_muscles)


def _nested_mapping(value: Mapping[str, object] | None, key: str) -> Mapping[str, object]:
    if value is None:
        return {}
    nested = value.get(key)
    return nested if isinstance(nested, Mapping) else {}


def _evidence_is_unavailable(value: object) -> bool:
    return isinstance(value, Mapping) and value.get("unavailable") is True


__all__ = [
    "WeeklyCoverage",
    "assess_weekly_coverage",
    "build_coverage_availability_evidence",
]
