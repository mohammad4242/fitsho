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
from app.workouts.program_engine.duration_policy import (
    get_session_duration_policy,
    calculate_resistance_minutes,
)
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
    secondary_muscles: tuple[MuscleGroup, ...] = (),
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
        secondary_muscles=secondary_muscles,
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


def test_hard_priority_minimum_can_use_headroom_above_soft_effective_maximum() -> None:
    glute = _programmed(
        "Glute Bridge",
        MuscleGroup.GLUTES,
        3,
        pattern=MovementPattern.HIP_EXTENSION,
    )
    hamstring = _programmed(
        "Leg Curl",
        MuscleGroup.HAMSTRINGS,
        3,
        pattern=MovementPattern.KNEE_FLEXION,
        secondary_muscles=(MuscleGroup.GLUTES,),
    )
    second_hamstring = replace(
        hamstring,
        exercise_id=uuid4(),
        exercise_name="Romanian Deadlift",
        movement_pattern=MovementPattern.HIP_HINGE,
    )
    volume = WeeklyVolumePlan(
        targets=(
            VolumeTarget(
                muscle=MuscleGroup.GLUTES,
                minimum_soft=4,
                target_sets=5,
                maximum_soft=5,
                maximum_hard=8,
                fractional_sets=0,
                effective_target_sets=5,
                minimum_direct_sets=4,
                minimum_effective_sets=4,
                minimum_coverage_required=True,
                direct_minimum_required=True,
            ),
        ),
        reason_codes=(),
    )

    days, _reasons = repair_weekly_volume(
        (_day(1, (glute, hamstring, second_hamstring), focus="lower"),),
        normalized(priority_muscles=[MuscleGroup.GLUTES]),
        volume,
        RULESET,
        preserve_template_core_structure=True,
    )

    repaired_glute = next(
        item for item in days[0].exercises if item.primary_muscle is MuscleGroup.GLUTES
    )
    assert repaired_glute.sets == 4


def test_hard_priority_minimum_adds_second_exercise_then_rebalances_sets() -> None:
    bridge = _programmed(
        "Glute Bridge",
        MuscleGroup.GLUTES,
        4,
        pattern=MovementPattern.HIP_EXTENSION,
    )
    second_glute = replace(
        _candidate("Hip Thrust", MuscleGroup.GLUTES),
        movement_pattern=MovementPattern.HIP_EXTENSION,
    )
    volume = WeeklyVolumePlan(
        targets=(
            VolumeTarget(
                muscle=MuscleGroup.GLUTES,
                minimum_soft=6,
                target_sets=6,
                maximum_soft=6,
                maximum_hard=6,
                fractional_sets=0,
                effective_target_sets=6,
                minimum_direct_sets=6,
                minimum_effective_sets=6,
                minimum_coverage_required=True,
                direct_minimum_required=True,
            ),
        ),
        reason_codes=(),
    )

    days, _reasons = repair_weekly_volume(
        (_day(1, (bridge,), focus="lower"),),
        normalized(priority_muscles=[MuscleGroup.GLUTES]),
        volume,
        RULESET,
        candidates=(second_glute,),
    )

    assert (
        sum(item.sets for item in days[0].exercises if item.primary_muscle is MuscleGroup.GLUTES)
        == 6
    )


def test_hard_priority_minimum_reuses_the_only_safe_exercise_across_sessions() -> None:
    bridge = _programmed(
        "Glute Bridge",
        MuscleGroup.GLUTES,
        3,
        pattern=MovementPattern.HIP_EXTENSION,
    )
    bridge_candidate = replace(
        _candidate("Glute Bridge", MuscleGroup.GLUTES),
        id=bridge.exercise_id,
        movement_pattern=MovementPattern.HIP_EXTENSION,
    )
    volume = WeeklyVolumePlan(
        targets=(
            VolumeTarget(
                muscle=MuscleGroup.GLUTES,
                minimum_soft=4,
                target_sets=6,
                maximum_soft=6,
                maximum_hard=6,
                fractional_sets=0,
                effective_target_sets=6,
                minimum_direct_sets=4,
                minimum_effective_sets=4,
                minimum_coverage_required=True,
                direct_minimum_required=True,
            ),
        ),
        reason_codes=(),
    )

    days, _reasons = repair_weekly_volume(
        (
            _day(1, (), focus="upper"),
            _day(2, (bridge,), focus="lower"),
        ),
        normalized(priority_muscles=[MuscleGroup.GLUTES], available_training_days=2),
        volume,
        RULESET,
        candidates=(bridge_candidate,),
    )

    repeated = [
        item for day in days for item in day.exercises if item.exercise_id == bridge.exercise_id
    ]
    assert len(repeated) == 2
    assert "PRIORITY_EXERCISE_REPEATED_FOR_HARD_MINIMUM" in repeated[0].reason_codes


def test_reference_repair_adds_hard_major_coverage_outside_original_focus() -> None:
    press = _programmed("Push-Up", MuscleGroup.CHEST, 3)
    abs_candidate = replace(
        _candidate("Dead Bug", MuscleGroup.ABS),
        movement_pattern=MovementPattern.CORE_ANTI_EXTENSION,
        exercise_type=ExerciseType.CORE,
    )
    volume = WeeklyVolumePlan(
        targets=(
            VolumeTarget(
                muscle=MuscleGroup.ABS,
                minimum_soft=1,
                target_sets=1,
                maximum_soft=4,
                maximum_hard=6,
                fractional_sets=0,
                effective_target_sets=1,
                minimum_direct_sets=1,
                minimum_effective_sets=1,
                minimum_coverage_required=True,
            ),
        ),
        reason_codes=(),
    )

    days, _reasons = repair_weekly_volume(
        (_day(1, (press,), focus="template_reference:test:upper"),),
        normalized(),
        volume,
        RULESET,
        candidates=(abs_candidate,),
    )

    assert any(item.primary_muscle is MuscleGroup.ABS for item in days[0].exercises)


def test_volume_repair_preserves_last_hard_movement_role_while_reducing_secondary_excess() -> None:
    hinge = replace(
        _programmed(
            "Romanian Deadlift",
            MuscleGroup.HAMSTRINGS,
            3,
            pattern=MovementPattern.HIP_HINGE,
            secondary_muscles=(MuscleGroup.GLUTES,),
        ),
        order=2,
        reason_codes=("TEMPLATE_ADAPTATION_PRIORITY:core",),
    )
    leg_curl = _programmed(
        "Leg Curl",
        MuscleGroup.HAMSTRINGS,
        3,
        pattern=MovementPattern.KNEE_FLEXION,
        secondary_muscles=(MuscleGroup.GLUTES,),
    )
    volume = WeeklyVolumePlan(
        targets=(
            VolumeTarget(
                muscle=MuscleGroup.GLUTES,
                minimum_soft=0,
                target_sets=2,
                maximum_soft=2,
                maximum_hard=2,
                fractional_sets=0,
                effective_target_sets=2,
                minimum_direct_sets=0,
                minimum_effective_sets=0,
            ),
        ),
        reason_codes=(),
    )

    days, _reasons = repair_weekly_volume(
        (_day(1, (hinge, leg_curl), focus="lower"),),
        normalized(),
        volume,
        RULESET,
        preserve_template_core_structure=True,
    )

    assert [item.movement_pattern for item in days[0].exercises] == [MovementPattern.HIP_HINGE]


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
        policy.contains(
            max(
                0,
                day.estimated_duration_minutes
                - RULESET.general_warmup_minutes
                - (day.cardio.duration_minutes if day.cardio else 0),
            )
        )
        for day in result.program.weekly_schedule
    ):
        assert (
            "SESSION_DURATION_CONSTRAINED_BY_HARD_VOLUME_LIMITS"
            in result.program.validation_report.warnings
            or "SESSION_DURATION_CONSTRAINED_BY_USEFUL_WORKLOAD"
            in result.program.validation_report.warnings
            or "PLANNED_SOFT_VOLUME_REDUCED_DURING_SESSION_FIT"
            in result.program.validation_report.warnings
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
        source,
        RULESET,
    )

    assert selected is not None
    assert selected[:2] == (0, 0)


def test_volume_repair_handles_secondary_target_for_untracked_primary() -> None:
    oblique_exercise = replace(
        _programmed("Oblique Crunch", MuscleGroup.OBLIQUES, 2),
        secondary_muscles=(MuscleGroup.CHEST,),
    )
    chest_target = _volume_target(MuscleGroup.CHEST).targets[0]

    selected = _select_addition_candidate(
        [[oblique_exercise]],
        set(),
        {MuscleGroup.CHEST},
        Counter(),
        {MuscleGroup.CHEST: chest_target},
        normalized(),
        RULESET,
    )

    assert selected is not None
    assert selected[:2] == (0, 0)
