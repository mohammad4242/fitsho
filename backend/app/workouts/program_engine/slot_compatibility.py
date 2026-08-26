from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.exercises.enums import ExerciseLabel, ExerciseType, MovementPattern, MuscleGroup
from app.workouts.program_engine.enums import CompatibilityLevel
from app.workouts.program_engine.substitution_policy import (
    ARM_PATTERNS,
    CORE_PATTERNS,
    HINGE_PATTERNS,
    KNEE_PATTERNS,
    LOWER_ACCESSORY_PATTERNS,
    PULL_PATTERNS,
    PUSH_PATTERNS,
    SHOULDER_PATTERNS,
    SubstitutionCause,
    allowed_movement_patterns,
)


class SemanticCandidate(Protocol):
    @property
    def movement_pattern(self) -> MovementPattern: ...

    @property
    def primary_muscle(self) -> MuscleGroup | None: ...

    @property
    def secondary_muscles(self) -> tuple[MuscleGroup, ...]: ...

    @property
    def exercise_type(self) -> ExerciseType: ...


def template_slot_allowed_patterns(
    pattern: MovementPattern,
    target_muscles: tuple[MuscleGroup, ...],
) -> frozenset[MovementPattern]:
    return allowed_movement_patterns(
        pattern,
        target_muscles,
        cause=SubstitutionCause.TEMPLATE_RECOVERY,
    )


@dataclass(frozen=True)
class SlotCompatibility:
    level: CompatibilityLevel
    reason_codes: tuple[str, ...]

    @property
    def compatible(self) -> bool:
        return self.level != CompatibilityLevel.HARD_INCOMPATIBLE


def evaluate_candidate_slot_compatibility(
    candidate: SemanticCandidate,
    *,
    allowed_patterns: frozenset[MovementPattern],
    target_muscles: frozenset[MuscleGroup] | None = None,
    day_focus: str | None = None,
    allow_full_body: bool = False,
) -> SlotCompatibility:
    pattern = candidate.movement_pattern
    if pattern is MovementPattern.OTHER:
        return SlotCompatibility(
            CompatibilityLevel.HARD_INCOMPATIBLE, ("SLOT_SEMANTIC_METADATA_INCOMPLETE",)
        )
    if pattern not in allowed_patterns:
        return SlotCompatibility(
            CompatibilityLevel.HARD_INCOMPATIBLE, ("SLOT_MOVEMENT_PATTERN_MISMATCH",)
        )

    _focus_patterns, focus_muscles = _scope_for_focus(day_focus)
    if day_focus is not None and pattern not in _focus_patterns:
        return SlotCompatibility(
            CompatibilityLevel.HARD_INCOMPATIBLE, ("SLOT_MOVEMENT_PATTERN_MISMATCH",)
        )

    effective_targets = target_muscles if target_muscles is not None else focus_muscles
    specialized = effective_targets is not None
    cross_region_compound = _looks_cross_region_compound(candidate)
    if (
        specialized
        and not allow_full_body
        and (ExerciseLabel.FULL_BODY in getattr(candidate, "labels", ()) or cross_region_compound)
    ):
        return SlotCompatibility(
            CompatibilityLevel.HARD_INCOMPATIBLE,
            ("SLOT_FULL_BODY_INCOMPATIBLE_WITH_SPECIALIZED_FOCUS",),
        )

    if effective_targets is None:
        return SlotCompatibility(CompatibilityLevel.PREFERRED, ())
    if candidate.primary_muscle in effective_targets:
        return SlotCompatibility(CompatibilityLevel.PREFERRED, ())
    if candidate.exercise_type is ExerciseType.COMPOUND and set(
        candidate.secondary_muscles
    ).intersection(effective_targets):
        return SlotCompatibility(
            CompatibilityLevel.VALID_BUT_SUBOPTIMAL,
            ("SLOT_COMPATIBLE_COMPOUND_SECONDARY_TARGET",),
        )
    return SlotCompatibility(CompatibilityLevel.HARD_INCOMPATIBLE, ("SLOT_SEMANTIC_MISMATCH",))


def is_candidate_compatible_with_slot(
    candidate: SemanticCandidate,
    *,
    allowed_patterns: frozenset[MovementPattern],
    target_muscles: frozenset[MuscleGroup] | None = None,
    day_focus: str | None = None,
    allow_full_body: bool = False,
) -> bool:
    return evaluate_candidate_slot_compatibility(
        candidate,
        allowed_patterns=allowed_patterns,
        target_muscles=target_muscles,
        day_focus=day_focus,
        allow_full_body=allow_full_body,
    ).compatible


def _looks_cross_region_compound(candidate: SemanticCandidate) -> bool:
    upper_prime_movers = {
        MuscleGroup.CHEST,
        MuscleGroup.SHOULDERS,
        MuscleGroup.BICEPS,
        MuscleGroup.TRICEPS,
    }
    lower = {
        MuscleGroup.GLUTES,
        MuscleGroup.QUADRICEPS,
        MuscleGroup.HAMSTRINGS,
        MuscleGroup.ADDUCTORS,
        MuscleGroup.ABDUCTORS,
        MuscleGroup.LEGS,
        MuscleGroup.CALVES,
    }
    muscles = set(candidate.secondary_muscles)
    if candidate.primary_muscle in lower:
        return candidate.exercise_type is ExerciseType.COMPOUND and bool(
            muscles & upper_prime_movers
        )
    if candidate.primary_muscle in upper_prime_movers | {
        MuscleGroup.BACK,
        MuscleGroup.TRAPS,
        MuscleGroup.FOREARMS,
    }:
        return candidate.exercise_type is ExerciseType.COMPOUND and bool(muscles & lower)
    return False


def _scope_for_focus(
    focus: str | None,
) -> tuple[frozenset[MovementPattern], frozenset[MuscleGroup] | None]:
    if focus is None or focus.startswith("template_reference"):
        return frozenset(MovementPattern) - {MovementPattern.OTHER}, None
    if focus.startswith("full_body"):
        return (
            PUSH_PATTERNS
            | PULL_PATTERNS
            | KNEE_PATTERNS
            | HINGE_PATTERNS
            | CORE_PATTERNS
            | LOWER_ACCESSORY_PATTERNS
            | SHOULDER_PATTERNS
            | ARM_PATTERNS
            | frozenset({MovementPattern.SHRUG}),
            None,
        )
    if focus.startswith("upper"):
        return (
            PUSH_PATTERNS
            | PULL_PATTERNS
            | ARM_PATTERNS
            | frozenset({MovementPattern.SHOULDER_ABDUCTION, MovementPattern.SHRUG}),
            frozenset(
                {
                    MuscleGroup.CHEST,
                    MuscleGroup.BACK,
                    MuscleGroup.SHOULDERS,
                    MuscleGroup.TRAPS,
                    MuscleGroup.BICEPS,
                    MuscleGroup.TRICEPS,
                }
            ),
        )
    if focus in {"lower", "legs"} or focus.startswith("lower"):
        return (
            KNEE_PATTERNS | HINGE_PATTERNS | CORE_PATTERNS | LOWER_ACCESSORY_PATTERNS,
            frozenset(
                {
                    MuscleGroup.QUADRICEPS,
                    MuscleGroup.HAMSTRINGS,
                    MuscleGroup.GLUTES,
                    MuscleGroup.CALVES,
                    MuscleGroup.ABS,
                }
            ),
        )
    scopes: dict[str, tuple[frozenset[MovementPattern], frozenset[MuscleGroup]]] = {
        "push": (
            PUSH_PATTERNS | frozenset({MovementPattern.ELBOW_EXTENSION}),
            frozenset({MuscleGroup.CHEST, MuscleGroup.SHOULDERS, MuscleGroup.TRICEPS}),
        ),
        "pull": (
            PULL_PATTERNS | frozenset({MovementPattern.ELBOW_FLEXION}),
            frozenset({MuscleGroup.BACK, MuscleGroup.BICEPS}),
        ),
        "chest_triceps": (
            PUSH_PATTERNS | frozenset({MovementPattern.ELBOW_EXTENSION}),
            frozenset({MuscleGroup.CHEST, MuscleGroup.TRICEPS}),
        ),
        "back_biceps": (
            PULL_PATTERNS | frozenset({MovementPattern.ELBOW_FLEXION}),
            frozenset({MuscleGroup.BACK, MuscleGroup.BICEPS}),
        ),
        "shoulders_traps": (
            SHOULDER_PATTERNS | frozenset({MovementPattern.HORIZONTAL_PULL, MovementPattern.SHRUG}),
            frozenset({MuscleGroup.SHOULDERS, MuscleGroup.TRAPS}),
        ),
        "quadriceps_calves": (
            KNEE_PATTERNS | frozenset({MovementPattern.CALF_RAISE}),
            frozenset({MuscleGroup.QUADRICEPS, MuscleGroup.CALVES}),
        ),
        "posterior_chain_core": (
            HINGE_PATTERNS | CORE_PATTERNS | frozenset({MovementPattern.KNEE_FLEXION}),
            frozenset({MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES, MuscleGroup.ABS}),
        ),
    }
    return scopes.get(
        focus,
        (PUSH_PATTERNS | PULL_PATTERNS | KNEE_PATTERNS | HINGE_PATTERNS | CORE_PATTERNS, None),
    )


def focus_scope(
    focus: str,
) -> tuple[frozenset[MovementPattern], frozenset[MuscleGroup] | None]:
    return _scope_for_focus(focus)
