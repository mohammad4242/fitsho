from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.exercises.enums import MovementPattern, MuscleGroup
from app.workouts.program_engine.effective_volume import calculate_effective_volume
from app.workouts.program_engine.rulesets.resistance_training_v1 import ProgramRuleset
from app.workouts.program_engine.schemas import WorkoutDay

_MAJOR_MUSCLES: tuple[MuscleGroup, ...] = (
    MuscleGroup.CHEST,
    MuscleGroup.BACK,
    MuscleGroup.SHOULDERS,
    MuscleGroup.QUADRICEPS,
    MuscleGroup.HAMSTRINGS,
    MuscleGroup.GLUTES,
)

_PATTERN_GROUPS: tuple[tuple[str, frozenset[MovementPattern]], ...] = (
    (
        "push",
        frozenset({MovementPattern.HORIZONTAL_PUSH, MovementPattern.VERTICAL_PUSH}),
    ),
    (
        "pull",
        frozenset({MovementPattern.HORIZONTAL_PULL, MovementPattern.VERTICAL_PULL}),
    ),
    (
        "knee",
        frozenset({MovementPattern.SQUAT, MovementPattern.LUNGE, MovementPattern.KNEE_EXTENSION}),
    ),
    (
        "hinge",
        frozenset({MovementPattern.HIP_HINGE, MovementPattern.HIP_EXTENSION}),
    ),
)

_PATTERN_MUSCLES: dict[str, frozenset[str]] = {
    "push": frozenset({"chest", "shoulders"}),
    "pull": frozenset({"back"}),
    "knee": frozenset({"quadriceps", "glutes"}),
    "hinge": frozenset({"hamstrings", "glutes"}),
}


@dataclass(frozen=True)
class WeeklyCoverage:
    metrics: dict[str, object]


def assess_weekly_coverage(
    days: tuple[WorkoutDay, ...],
    aggregate_metrics: Mapping[str, object] | None = None,
    *,
    ruleset: ProgramRuleset,
) -> WeeklyCoverage:
    """Assess actual full-body coverage and preserve explicit unavailable causes."""

    if not any(_is_full_body_claim(day) for day in days):
        return WeeklyCoverage(_metrics("not_applicable"))

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
    unavailable_muscles = set(missing_muscles).intersection(
        _metric_strings(aggregate_metrics, "unavailable_muscle_coverage")
    )

    covered_patterns: list[str] = []
    missing_patterns: list[str] = []
    unavailable_patterns: list[str] = []
    relaxed_groups = _relaxed_groups(aggregate_metrics)
    for name, patterns in _PATTERN_GROUPS:
        if any(item.movement_pattern in patterns for day in days for item in day.exercises):
            covered_patterns.append(name)
            continue
        missing_patterns.append(name)
        if frozenset(
            pattern.value for pattern in patterns
        ) in relaxed_groups or unavailable_muscles.intersection(_PATTERN_MUSCLES[name]):
            unavailable_patterns.append(name)

    unavailable_by_pattern = set().union(*(_PATTERN_MUSCLES[name] for name in unavailable_patterns))
    unavailable_muscles.update(set(missing_muscles).intersection(unavailable_by_pattern))
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
) -> dict[str, object]:
    claimed = status != "not_applicable"
    return {
        "status": status,
        "claimed_full_body": claimed,
        "claimed_balanced": status == "satisfied",
        "fully_balanced": status == "satisfied",
        "required_patterns": tuple(name for name, _patterns in _PATTERN_GROUPS),
        "covered_patterns": covered_patterns,
        "missing_patterns": tuple(missing_patterns),
        "unavailable_patterns": tuple(unavailable_patterns),
        "major_muscles": tuple(muscle.value for muscle in _MAJOR_MUSCLES),
        "covered_major_muscles": covered_muscles,
        "missing_major_muscles": tuple(missing_muscles),
        "unavailable_major_muscles": tuple(unavailable_muscles),
        "reason_codes": reason_codes,
        "constraint_reason_codes": reason_codes,
    }


def _is_full_body_claim(day: WorkoutDay) -> bool:
    if day.focus.startswith("full_body"):
        return True
    if not day.focus.startswith("template_reference"):
        return False
    if day.template_structure_focus != "full_body":
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
    targets = set(day.template_target_muscles)
    return bool(targets.intersection(upper) and targets.intersection(lower))


def _metric_strings(
    metrics: Mapping[str, object] | None,
    key: str,
) -> set[str]:
    if metrics is None:
        return set()
    value = metrics.get(key, ())
    return (
        {str(item) for item in value} if isinstance(value, (tuple, list, set, frozenset)) else set()
    )


def _relaxed_groups(metrics: Mapping[str, object] | None) -> set[frozenset[str]]:
    if metrics is None:
        return set()
    value = metrics.get("relaxed_required_pattern_groups", ())
    return (
        {
            frozenset(str(pattern) for pattern in group)
            for group in value
            if isinstance(group, (tuple, list, set, frozenset))
        }
        if isinstance(value, (tuple, list, set, frozenset))
        else set()
    )


__all__ = ["WeeklyCoverage", "assess_weekly_coverage"]
