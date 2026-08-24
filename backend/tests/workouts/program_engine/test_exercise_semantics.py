from dataclasses import FrozenInstanceError, replace
from uuid import uuid4

import pytest

from app.exercises.enums import (
    Difficulty,
    Equipment,
    ExerciseType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.workouts.program_engine.enums import BodyPosition, Laterality
from app.workouts.program_engine.exercise_semantics import ExerciseRoleSignature
from app.workouts.program_engine.schemas import ExerciseCandidate


def _candidate(**overrides: object) -> ExerciseCandidate:
    values: dict[str, object] = {
        "id": uuid4(),
        "name": "Incline Dumbbell Press",
        "primary_muscle": MuscleGroup.CHEST,
        "muscle_focus": MuscleFocus.UPPER_CHEST,
        "secondary_muscles": (MuscleGroup.TRICEPS, MuscleGroup.SHOULDERS),
        "movement_pattern": MovementPattern.HORIZONTAL_PUSH,
        "exercise_type": ExerciseType.COMPOUND,
        "equipment": frozenset({Equipment.DUMBBELL, Equipment.BENCH}),
        "difficulty": Difficulty.INTERMEDIATE,
        "body_position": BodyPosition.SUPPORTED,
        "laterality": Laterality.BILATERAL,
        "substitution_group": "horizontal_press_incline",
    }
    values.update(overrides)
    return ExerciseCandidate(**values)  # type: ignore[arg-type]


def test_role_signature_is_canonical_and_independent_of_display_identity() -> None:
    source = _candidate()
    same_role = replace(
        source,
        id=uuid4(),
        name="پرس بالا سینه دمبل",
        secondary_muscles=(MuscleGroup.SHOULDERS, MuscleGroup.TRICEPS),
        display_snapshot={"name_fa": "پرس بالا سینه دمبل"},
    )

    first = ExerciseRoleSignature.from_candidate(source)
    second = ExerciseRoleSignature.from_candidate(same_role)

    assert first == second
    assert first.secondary_muscles == (MuscleGroup.SHOULDERS, MuscleGroup.TRICEPS)


def test_role_signature_is_immutable() -> None:
    signature = ExerciseRoleSignature.from_candidate(_candidate())

    with pytest.raises(FrozenInstanceError):
        signature.substitution_group = "changed"
