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
from app.workouts.program_engine import exercise_semantics
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


def test_near_equivalent_squat_roles_are_redundant_without_meaningful_distinction() -> None:
    barbell_squat = _candidate(
        name="Barbell Squat",
        movement_pattern=MovementPattern.SQUAT,
        primary_muscle=MuscleGroup.QUADRICEPS,
        muscle_focus=MuscleFocus.GENERAL_QUADRICEPS,
        secondary_muscles=(MuscleGroup.GLUTES,),
        equipment=frozenset({Equipment.BARBELL}),
        body_position=BodyPosition.STANDING,
        substitution_group="squat_free_weight",
    )
    generic_squat = replace(barbell_squat, id=uuid4(), name="Squat")

    near_equivalent = getattr(exercise_semantics, "near_equivalent_exercises", None)
    assert near_equivalent is not None
    assert near_equivalent(barbell_squat, generic_squat)


def test_near_equivalent_policy_preserves_distinct_training_roles() -> None:
    squat = _candidate(
        movement_pattern=MovementPattern.SQUAT,
        primary_muscle=MuscleGroup.QUADRICEPS,
        muscle_focus=MuscleFocus.GENERAL_QUADRICEPS,
        substitution_group="squat_free_weight",
    )
    lunge = replace(
        squat,
        id=uuid4(),
        movement_pattern=MovementPattern.LUNGE,
        laterality=Laterality.UNILATERAL,
        substitution_group="lunge_split_stance",
    )
    flat_press = replace(
        squat,
        id=uuid4(),
        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        primary_muscle=MuscleGroup.CHEST,
        muscle_focus=MuscleFocus.MID_CHEST,
        substitution_group="horizontal_press_flat",
    )
    incline_press = replace(
        flat_press,
        id=uuid4(),
        muscle_focus=MuscleFocus.UPPER_CHEST,
        substitution_group="horizontal_press_incline",
    )

    near_equivalent = getattr(exercise_semantics, "near_equivalent_exercises", None)
    assert near_equivalent is not None
    assert not near_equivalent(squat, lunge)
    assert not near_equivalent(flat_press, incline_press)
