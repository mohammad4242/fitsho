"""Canonical exercise-role semantics for deterministic substitution."""

from __future__ import annotations

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
