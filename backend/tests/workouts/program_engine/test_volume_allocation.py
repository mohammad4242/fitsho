from collections import Counter
from dataclasses import replace
from uuid import uuid4

import pytest

from app.exercises.enums import (
    Difficulty,
    Equipment,
    ExerciseType,
    MovementPattern,
    MuscleGroup,
)
from app.workouts.program_engine.duration_policy import get_session_duration_policy
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.prescription import estimate_exercise_minutes
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    ProgrammedExercise,
    VolumeTarget,
    WeeklyVolumePlan,
    WorkoutDay,
)
from app.workouts.program_engine.volume_repair import (
    _select_addition_candidate,
    repair_weekly_volume,
)
from tests.workouts.program_engine.golden_fixtures import full_catalog, golden_scenarios
from tests.workouts.program_engine.test_selection_sessions import normalized


def _programmed(
    name: str,
    muscle: MuscleGroup,
    sets: int,
    *,
    exercise_type: ExerciseType = ExerciseType.COMPOUND,
    pattern: MovementPattern = MovementPattern.HORIZONTAL_PUSH,
) -> ProgrammedExercise:
    return ProgrammedExercise(
        exercise_id=uuid4(),
        exercise_name=name,
        order=1,
        sets=sets,
        rep_min=8,
        rep_max=12,
        target_rir=2,
        rest_seconds=90,
        estimated_minutes=8,
        reason_codes=("TEST",),
        movement_pattern=pattern,
        primary_muscle=muscle,
        exercise_type=exercise_type,
    )


def _day(index: int, exercises: tuple[ProgrammedExercise, ...], focus: str = "upper") -> WorkoutDay:
    return WorkoutDay(
        day_index=index,
        weekday=index,
        title=f"Day {index}",
        focus=focus,
        estimated_duration_minutes=20,
        exercises=exercises,
    )


def _volume_target(muscle: MuscleGroup, target_sets: int = 8) -> WeeklyVolumePlan:
    return WeeklyVolumePlan(
        targets=(
            VolumeTarget(
                muscle=muscle,
                minimum_soft=2,
                target_sets=target_sets,
                maximum_soft=target_sets,
                maximum_hard=target_sets,
                fractional_sets=0,
                effective_target_sets=target_sets,
                minimum_direct_sets=2,
                minimum_effective_sets=2,
            ),
        ),
        reason_codes=(),
    )


def _candidate(name: str, muscle: MuscleGroup) -> ExerciseCandidate:
    return ExerciseCandidate(
        id=uuid4(),
        name=name,
        primary_muscle=muscle,
        secondary_muscles=(),
        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        exercise_type=ExerciseType.COMPOUND,
        equipment=frozenset({Equipment.BODYWEIGHT}),
        difficulty=Difficulty.BEGINNER,
    )


def test_volume_repair_uses_a_second_exercise_before_dumping_sets() -> None:
    first = _programmed("Push-Up", MuscleGroup.CHEST, 4)
    second = _candidate("Chest Press", MuscleGroup.CHEST)

    days, reasons = repair_weekly_volume(
        (_day(1, (first,)),),
        normalized(),
        _volume_target(MuscleGroup.CHEST),
        RULESET,
        candidates=(second,),
    )

    chest = [
        item for day in days for item in day.exercises if item.primary_muscle is MuscleGroup.CHEST
    ]
    # Under new rules (min 3, session max 6), Push-Up takes 4 sets, leaving 2 slots.
    # 2 < minimum_working_sets (3), so Chest Press cannot be added — only 1 exercise.
    assert len(chest) == 1
    assert max(item.sets for item in chest) <= 5


def test_volume_repair_spreads_existing_sets_across_days() -> None:
    first = _programmed("Push-Up", MuscleGroup.CHEST, 2)

    days, _ = repair_weekly_volume(
        (_day(1, (first,)), _day(2, (_programmed("Push-Up", MuscleGroup.CHEST, 2),))),
        normalized(available_training_days=2),
        _volume_target(MuscleGroup.CHEST),
        RULESET,
    )

    sets_by_day = [day.exercises[0].sets for day in days]
    assert max(sets_by_day) <= 5
    assert max(sets_by_day) - min(sets_by_day) <= 1


@pytest.mark.parametrize("name", ["Glute Bridge", "Dumbbell Lunge", "Dead Bug"])
def test_named_regressions_do_not_reach_six_sets(name: str) -> None:
    muscle = MuscleGroup.GLUTES if name == "Glute Bridge" else MuscleGroup.QUADRICEPS
    pattern = (
        MovementPattern.HIP_EXTENSION
        if name == "Glute Bridge"
        else MovementPattern.LUNGE
        if name == "Dumbbell Lunge"
        else MovementPattern.CORE_ANTI_EXTENSION
    )
    exercise_type = ExerciseType.CORE if name == "Dead Bug" else ExerciseType.COMPOUND
    if name == "Dead Bug":
        muscle = MuscleGroup.ABS

    days, _ = repair_weekly_volume(
        (_day(1, (_programmed(name, muscle, 6, exercise_type=exercise_type, pattern=pattern),)),),
        normalized(),
        _volume_target(muscle, target_sets=6),
        RULESET,
    )

    assert days[0].exercises[0].sets <= 5


def test_limited_catalog_reduces_soft_target_with_reason_code() -> None:
    days, reasons = repair_weekly_volume(
        (_day(1, (_programmed("Push-Up", MuscleGroup.CHEST, 4),)),),
        normalized(),
        _volume_target(MuscleGroup.CHEST, target_sets=8),
        RULESET,
    )

    assert days[0].exercises[0].sets <= 5
    assert "VOLUME_REPAIR_SOFT_TARGET_REDUCED" in reasons


def test_priority_muscle_keeps_extra_volume_without_set_dumping() -> None:
    result = generate_program(
        golden_scenarios()["intermediate_5_days_shoulder_priority"],
        full_catalog(),
        RULESET,
    )

    assert result.program is not None, result.errors
    direct = result.program.aggregate_metrics["weekly_direct_sets_by_muscle"]
    assert direct[MuscleGroup.SHOULDERS.value] > direct[MuscleGroup.CHEST.value]
    assert all(item.sets <= 4 for day in result.program.weekly_schedule for item in day.exercises)


def test_generate_program_preserves_volume_and_duration_constraints_without_set_dump() -> None:
    result = generate_program(
        golden_scenarios()["novice_3_days_fat_loss_low_impact"],
        full_catalog(),
        RULESET,
    )

    assert result.program is not None, result.errors
    assert all(item.sets <= 4 for day in result.program.weekly_schedule for item in day.exercises)
    policy = get_session_duration_policy(
        int(result.program.user_profile_snapshot["session_duration_minutes"])
    )
    if not all(
        policy.contains_total(day.estimated_duration_minutes, RULESET.general_warmup_minutes)
        for day in result.program.weekly_schedule
    ):
        assert "SESSION_DURATION_CONSTRAINED_BY_HARD_VOLUME_LIMITS" in (
            result.program.validation_report.warnings
        )
    metrics = result.program.aggregate_metrics
    assert all(
        value <= max(3, metrics["volume_ranges_by_muscle"][muscle]["maximum_hard"]) + 4
        for muscle, value in metrics["weekly_effective_sets_by_muscle"].items()
        if muscle in metrics["volume_ranges_by_muscle"]
    )
    assert all(
        value <= max(3, metrics["volume_ranges_by_muscle"][muscle]["maximum_hard"])
        for muscle, value in metrics["weekly_direct_sets_by_muscle"].items()
        if muscle in metrics["volume_ranges_by_muscle"]
    )


def test_volume_repair_accepts_valid_increment_between_plus_five_and_plus_ten() -> None:
    source = normalized(session_duration_minutes=60)
    target = replace(
        _programmed("Target", MuscleGroup.CHEST, 2),
        estimated_minutes=estimate_exercise_minutes(2, 90, 0, RULESET),
    )
    fillers = tuple(
        replace(
            _programmed(f"Filler {index}", MuscleGroup.BACK, 4),
            estimated_minutes=8,
        )
        for index in range(6)
    ) + (
        replace(
            _programmed("Filler final", MuscleGroup.BACK, 3),
            rest_seconds=120,
            estimated_minutes=estimate_exercise_minutes(3, 120, 0, RULESET),
        ),
    )
    volume_target = _volume_target(MuscleGroup.CHEST).targets[0]

    selected = _select_addition_candidate(
        [[target, *fillers]],
        {MuscleGroup.CHEST},
        set(),
        Counter({MuscleGroup.CHEST.value: 2}),
        {MuscleGroup.CHEST: volume_target},
        (0,),
        source,
        RULESET,
    )

    assert selected is not None
    assert selected[:2] == (0, 0)
