from uuid import uuid4

import pytest

from app.exercises.enums import MovementPattern, MuscleGroup
from app.workouts.program_engine.effective_volume import calculate_effective_volume
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import ProgrammedExercise


def programmed_exercise(
    primary: MuscleGroup,
    secondary: tuple[MuscleGroup, ...],
    sets: int,
) -> ProgrammedExercise:
    return ProgrammedExercise(
        exercise_id=uuid4(),
        exercise_name="test exercise",
        order=1,
        sets=sets,
        rep_min=8,
        rep_max=12,
        target_rir=2,
        rest_seconds=90,
        estimated_minutes=8,
        reason_codes=("TEST",),
        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        primary_muscle=primary,
        secondary_muscles=secondary,
    )


def test_primary_and_secondary_sets_receive_distinct_effective_credit() -> None:
    volume = calculate_effective_volume(
        (programmed_exercise(MuscleGroup.CHEST, (MuscleGroup.TRICEPS,), 3),),
        RULESET,
    )

    assert volume.direct_sets_by_muscle == {MuscleGroup.CHEST.value: 3}
    assert volume.secondary_sets_by_muscle == {MuscleGroup.TRICEPS.value: 1.5}
    assert volume.effective_sets_by_muscle == {
        MuscleGroup.CHEST.value: 3.0,
        MuscleGroup.TRICEPS.value: 1.5,
    }


def test_compound_exercise_credits_all_secondary_muscles_once() -> None:
    volume = calculate_effective_volume(
        (
            programmed_exercise(
                MuscleGroup.CHEST,
                (
                    MuscleGroup.BICEPS,
                    MuscleGroup.TRICEPS,
                    MuscleGroup.TRAPS,
                    MuscleGroup.FOREARMS,
                ),
                4,
            ),
        ),
        RULESET,
    )

    assert volume.effective_sets_by_muscle == {
        MuscleGroup.CHEST.value: 4.0,
        MuscleGroup.BICEPS.value: 2.0,
        MuscleGroup.TRICEPS.value: 2.0,
        MuscleGroup.TRAPS.value: 2.0,
        MuscleGroup.FOREARMS.value: 2.0,
    }


def test_same_muscle_is_not_double_counted_as_primary_and_secondary() -> None:
    volume = calculate_effective_volume(
        (
            programmed_exercise(
                MuscleGroup.CHEST,
                (MuscleGroup.CHEST, MuscleGroup.TRICEPS, MuscleGroup.TRICEPS),
                3,
            ),
        ),
        RULESET,
    )

    assert volume.effective_sets_by_muscle[MuscleGroup.CHEST.value] == 3.0
    assert volume.effective_sets_by_muscle[MuscleGroup.TRICEPS.value] == 1.5
    assert MuscleGroup.CHEST.value not in volume.secondary_sets_by_muscle


def test_effective_volume_calculation_is_deterministic() -> None:
    exercises = (
        programmed_exercise(MuscleGroup.CHEST, (MuscleGroup.TRICEPS,), 3),
        programmed_exercise(MuscleGroup.BACK, (MuscleGroup.BICEPS,), 4),
    )

    first = calculate_effective_volume(exercises, RULESET)
    second = calculate_effective_volume(exercises, RULESET)

    assert first == second


def test_effective_volume_uses_ruleset_credit_values() -> None:
    custom_ruleset = RULESET.__class__(
        **{
            **RULESET.__dict__,
            "primary_set_credit": 1.0,
            "secondary_set_credit": 0.25,
        }
    )

    volume = calculate_effective_volume(
        (programmed_exercise(MuscleGroup.CHEST, (MuscleGroup.TRICEPS,), 4),),
        custom_ruleset,
    )

    assert volume.effective_sets_by_muscle[MuscleGroup.CHEST.value] == pytest.approx(4.0)
    assert volume.effective_sets_by_muscle[MuscleGroup.TRICEPS.value] == pytest.approx(1.0)
