"""Canonical exercise-role semantics for deterministic substitution."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from app.exercises.enums import Equipment, ExerciseType, MovementPattern, MuscleFocus, MuscleGroup
from app.workouts.program_engine.enums import BodyPosition, Laterality


class ExerciseRoleSource(Protocol):
    @property
    def movement_pattern(self) -> MovementPattern: ...

    @property
    def primary_muscle(self) -> MuscleGroup | None: ...

    @property
    def muscle_focus(self) -> MuscleFocus | None: ...

    @property
    def exercise_type(self) -> ExerciseType: ...

    @property
    def secondary_muscles(self) -> tuple[MuscleGroup, ...]: ...

    @property
    def body_position(self) -> BodyPosition: ...

    @property
    def laterality(self) -> Laterality: ...

    @property
    def substitution_group(self) -> str | None: ...

    @property
    def equipment(self) -> frozenset[Equipment]: ...


@dataclass(frozen=True, slots=True)
class ExerciseRoleSignature:
    """Structured description of what an exercise does, without user constraints."""

    movement_pattern: MovementPattern
    primary_muscle: MuscleGroup | None
    muscle_focus: MuscleFocus | None
    exercise_type: ExerciseType
    secondary_muscles: tuple[MuscleGroup, ...]
    body_position: BodyPosition
    laterality: Laterality
    substitution_group: str | None
    equipment: frozenset[Equipment] = frozenset()

    @classmethod
    def from_candidate(cls, candidate: ExerciseRoleSource) -> ExerciseRoleSignature:
        return cls(
            movement_pattern=candidate.movement_pattern,
            primary_muscle=candidate.primary_muscle,
            muscle_focus=candidate.muscle_focus,
            exercise_type=candidate.exercise_type,
            secondary_muscles=tuple(
                sorted(set(candidate.secondary_muscles), key=lambda muscle: muscle.value)
            ),
            body_position=candidate.body_position,
            laterality=candidate.laterality,
            substitution_group=candidate.substitution_group,
            equipment=frozenset(candidate.equipment),
        )

    @property
    def canonical_family(self) -> str:
        return _canonical_semantic_family(self)


SEMANTIC_NEAR_DUPLICATE_REASON = "SEMANTIC_NEAR_DUPLICATE_REJECTED"

_LEGACY_BROAD_GROUPS = frozenset(pattern.value for pattern in MovementPattern)
_DISTINCT_SQUAT_FAMILIES = frozenset(
    {"squat_wide_stance", "squat_supported_machine", "squat_sissy"}
)
_DISTINCT_HINGE_FAMILIES = frozenset(
    {"hip_hinge_reverse_hyperextension", "hip_hinge_good_morning"}
)


def _canonical_semantic_family(signature: ExerciseRoleSignature) -> str:
    """Normalize equipment-specific metadata into a programming-role family."""

    group = signature.substitution_group
    if group in _LEGACY_BROAD_GROUPS:
        group = None
    if signature.movement_pattern is MovementPattern.SQUAT:
        if group in _DISTINCT_SQUAT_FAMILIES:
            return group
        return "squat_primary"
    if signature.movement_pattern is MovementPattern.HIP_HINGE:
        if group in _DISTINCT_HINGE_FAMILIES:
            return group
        return "hip_hinge_primary"
    if signature.movement_pattern is MovementPattern.HORIZONTAL_PUSH and group is not None:
        if "push_up" in group or group == "pushup":
            return "horizontal_push_push_up"
    return group or (
        f"{signature.movement_pattern.value}:"
        f"{signature.primary_muscle.value if signature.primary_muscle is not None else 'none'}:"
        f"{signature.exercise_type.value}"
    )


def near_equivalent_exercises(
    first: ExerciseRoleSource,
    second: ExerciseRoleSource,
) -> bool:
    """Return whether two exercises have the same meaningful training role."""

    left = ExerciseRoleSignature.from_candidate(first)
    right = ExerciseRoleSignature.from_candidate(second)
    if (
        left.movement_pattern is not right.movement_pattern
        or left.primary_muscle is not right.primary_muscle
        or left.exercise_type is not right.exercise_type
    ):
        return False
    if left.canonical_family != right.canonical_family:
        return False
    if (
        left.muscle_focus is not None
        and right.muscle_focus is not None
        and left.muscle_focus is not right.muscle_focus
    ):
        return False
    if left.body_position is not right.body_position or left.laterality is not right.laterality:
        return False
    if left.canonical_family.startswith(("squat_", "hip_hinge_", "horizontal_push_push_up")):
        return True
    if left.equipment != right.equipment:
        return False
    if left.secondary_muscles != right.secondary_muscles:
        return False
    return bool(
        left.muscle_focus is not None
        or left.secondary_muscles
        or left.body_position is not BodyPosition.STANDING
        or left.laterality is not Laterality.BILATERAL
    )


def has_near_equivalent(
    exercise: ExerciseRoleSource,
    others: Iterable[ExerciseRoleSource],
) -> bool:
    return any(near_equivalent_exercises(exercise, other) for other in others)


def is_primary_working_compound(exercise: ExerciseRoleSource) -> bool:
    return exercise.exercise_type is ExerciseType.COMPOUND and exercise.movement_pattern in {
        MovementPattern.HORIZONTAL_PUSH,
        MovementPattern.VERTICAL_PUSH,
        MovementPattern.HORIZONTAL_PULL,
        MovementPattern.VERTICAL_PULL,
    }
