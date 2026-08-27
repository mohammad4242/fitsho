"""Canonical exercise-role semantics for deterministic substitution."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from app.exercises.enums import ExerciseType, MovementPattern, MuscleFocus, MuscleGroup
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
        )


SEMANTIC_NEAR_DUPLICATE_REASON = "SEMANTIC_NEAR_DUPLICATE_REJECTED"


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
    if (
        left.substitution_group is not None
        and right.substitution_group is not None
        and left.substitution_group != right.substitution_group
    ):
        return False
    if (
        left.muscle_focus is not None
        and right.muscle_focus is not None
        and left.muscle_focus is not right.muscle_focus
    ):
        return False
    if left.secondary_muscles != right.secondary_muscles:
        return False
    if left.body_position is not right.body_position or left.laterality is not right.laterality:
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
