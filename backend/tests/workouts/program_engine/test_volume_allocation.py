from collections import Counter
from dataclasses import replace
from uuid import uuid4

import pytest

from app.exercises.enums import (
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseType,
    MovementPattern,
    MuscleGroup,
)
from app.workouts.program_engine.duration_policy import get_session_duration_policy
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal
from app.workouts.program_engine.prescription import estimate_exercise_minutes
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    ProgrammedExercise,
    VolumeTarget,
    WeeklyVolumePlan,
    WorkoutDay,
)
from app.workouts.program_engine.substitution_engine import SubstitutionDecision
from app.workouts.program_engine.supplemental_policy import main_exercise_count
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

    days, _ = repair_weekly_volume(
        (_day(1, (first,)),),
        normalized(),
        _volume_target(MuscleGroup.CHEST),
        RULESET,
        candidates=(second,),
    )

    chest = [
        item for day in days for item in day.exercises if item.primary_muscle is MuscleGroup.CHEST
    ]
    assert len(chest) == 2
    assert sum(item.sets for item in chest) == 8
    assert all(item.sets <= RULESET.max_working_sets_per_exercise_absolute for item in chest)


def test_volume_repair_allows_twelve_direct_sets_for_one_muscle_in_session() -> None:
    exercises = tuple(
        _programmed(f"Chest Exercise {index}", MuscleGroup.CHEST, 4) for index in range(3)
    )

    days, _ = repair_weekly_volume(
        (_day(1, exercises),),
        normalized(),
        _volume_target(MuscleGroup.CHEST, target_sets=12),
        RULESET,
    )

    chest = tuple(item for item in days[0].exercises if item.primary_muscle is MuscleGroup.CHEST)
    assert sum(item.sets for item in chest) == 12
    assert all(item.sets <= RULESET.max_working_sets_per_exercise_absolute for item in chest)


def test_volume_repair_reduces_more_than_twelve_direct_sets_in_one_session() -> None:
    exercises = tuple(
        _programmed(f"Chest Exercise {index}", MuscleGroup.CHEST, 4) for index in range(4)
    )

    days, _ = repair_weekly_volume(
        (_day(1, exercises),),
        normalized(),
        _volume_target(MuscleGroup.CHEST, target_sets=16),
        RULESET,
    )

    chest_sets = sum(
        item.sets for item in days[0].exercises if item.primary_muscle is MuscleGroup.CHEST
    )
    assert chest_sets == 12


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


def test_hard_priority_minimum_does_not_reuse_exercise_on_incompatible_day() -> None:
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
    assert len(repeated) == 1
    assert all(item.primary_muscle is not MuscleGroup.GLUTES for item in days[0].exercises)


def test_hard_priority_addition_prefers_a_compatible_day() -> None:
    existing = _programmed("Push-Up", MuscleGroup.CHEST, 2)
    addition = _candidate("Incline Push-Up", MuscleGroup.CHEST)
    volume = WeeklyVolumePlan(
        targets=(
            VolumeTarget(
                muscle=MuscleGroup.CHEST,
                minimum_soft=4,
                target_sets=4,
                maximum_soft=6,
                maximum_hard=6,
                fractional_sets=0,
                effective_target_sets=4,
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
            _day(1, (), focus="back_biceps"),
            _day(2, (existing,), focus="chest_triceps"),
        ),
        normalized(priority_muscles=[MuscleGroup.CHEST], available_training_days=2),
        volume,
        RULESET,
        candidates=(addition,),
    )

    assert all(item.primary_muscle is not MuscleGroup.CHEST for item in days[0].exercises)
    assert any(item.exercise_id == addition.id for item in days[1].exercises)


def test_volume_repair_substitutions_are_hard_safe_and_keep_strength_role_order() -> None:
    target = replace(
        _candidate("Dumbbell Press", MuscleGroup.CHEST),
        equipment=frozenset({Equipment.DUMBBELL}),
    )
    primary_strength_alternative = replace(
        _candidate("Dumbbell Press Alternative", MuscleGroup.CHEST),
        equipment=frozenset({Equipment.DUMBBELL}),
        fatigue_cost=5,
    )
    secondary_bodyweight_alternative = replace(
        _candidate("Push-Up Alternative", MuscleGroup.CHEST),
        fatigue_cost=1,
    )
    blocked_alternative = replace(
        _candidate("Blocked Press", MuscleGroup.CHEST),
        caution_tags=frozenset({ExerciseCautionTag.SHOULDER_INTERNAL_ROTATION}),
    )
    initial = _programmed("Existing Press", MuscleGroup.CHEST, 3)
    volume = replace(
        _volume_target(MuscleGroup.CHEST, target_sets=6).targets[0],
        minimum_direct_sets=6,
        minimum_effective_sets=6,
        effective_target_sets=6,
    )

    substitution_decisions: list[SubstitutionDecision] = []
    days, _reasons = repair_weekly_volume(
        (_day(1, (initial,), focus="upper"),),
        normalized(
            primary_goal=Goal.STRENGTH,
            preferred_exercises=[target.id],
            blocked_caution_tags=[ExerciseCautionTag.SHOULDER_INTERNAL_ROTATION],
        ),
        WeeklyVolumePlan(targets=(volume,), reason_codes=()),
        RULESET,
        candidates=(
            target,
            primary_strength_alternative,
            secondary_bodyweight_alternative,
            blocked_alternative,
        ),
        substitution_decisions=substitution_decisions,
    )

    added = next(item for item in days[0].exercises if item.exercise_id == target.id)
    assert added.substitution_exercise_ids == (
        primary_strength_alternative.id,
        secondary_bodyweight_alternative.id,
    )
    assert blocked_alternative.id not in added.substitution_exercise_ids
    assert len(substitution_decisions) == 1
    assert substitution_decisions[0].target_exercise_id == target.id
    candidates_by_id = {
        item.id: item
        for item in (
            primary_strength_alternative,
            secondary_bodyweight_alternative,
        )
    }
    assert all(
        candidates_by_id[item_id].primary_muscle is target.primary_muscle
        and candidates_by_id[item_id].movement_pattern is target.movement_pattern
        and candidates_by_id[item_id].exercise_type is target.exercise_type
        for item_id in added.substitution_exercise_ids
    )


def test_reference_repair_does_not_add_hard_coverage_outside_original_focus() -> None:
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

    days, reasons = repair_weekly_volume(
        (_day(1, (press,), focus="template_reference:test:upper"),),
        normalized(),
        volume,
        RULESET,
        candidates=(abs_candidate,),
    )

    assert all(item.primary_muscle is not MuscleGroup.ABS for item in days[0].exercises)
    assert "VOLUME_REPAIR_HARD_MINIMUM_UNSATISFIED" in reasons


def test_volume_repair_reduces_unclassified_excess_preserving_hard_role() -> None:
    hinge = replace(
        _programmed(
            "Romanian Deadlift",
            MuscleGroup.HAMSTRINGS,
            3,
            pattern=MovementPattern.HIP_HINGE,
            secondary_muscles=(MuscleGroup.TRAPS,),
        ),
        order=2,
        reason_codes=("TEMPLATE_ADAPTATION_PRIORITY:core",),
    )
    leg_curl = _programmed(
        "Leg Curl",
        MuscleGroup.HAMSTRINGS,
        3,
        pattern=MovementPattern.KNEE_FLEXION,
        secondary_muscles=(MuscleGroup.TRAPS,),
    )
    volume = WeeklyVolumePlan(
        targets=(
            VolumeTarget(
                muscle=MuscleGroup.TRAPS,
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
    resistance_minutes = {
        day.day_index: max(
            0,
            day.estimated_duration_minutes
            - RULESET.general_warmup_minutes
            - (day.cardio.duration_minutes if day.cardio else 0),
        )
        for day in result.program.weekly_schedule
    }
    outliers = tuple(
        day
        for day in result.program.weekly_schedule
        if not policy.contains(resistance_minutes[day.day_index])
    )
    if outliers and not all(
        resistance_minutes[day.day_index] < policy.minimum_minutes
        and main_exercise_count(day.exercises) >= RULESET.minimum_exercises_per_session
        for day in outliers
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
        (_day(1, (target, *fillers)),),
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
        (_day(1, (oblique_exercise,)),),
        set(),
        {MuscleGroup.CHEST},
        Counter(),
        {MuscleGroup.CHEST: chest_target},
        normalized(),
        RULESET,
    )

    assert selected is not None
    assert selected[:2] == (0, 0)


def test_volume_repair_does_not_add_main_above_short_session_ceiling() -> None:
    existing = (
        _programmed("Existing Chest", MuscleGroup.CHEST, 5),
        _programmed("Existing Back", MuscleGroup.BACK, 5),
        _programmed("Existing Shoulders", MuscleGroup.SHOULDERS, 5),
        _programmed("Existing Triceps", MuscleGroup.TRICEPS, 5),
    )
    candidate = _candidate("Fifth Chest Exercise", MuscleGroup.CHEST)
    target = replace(
        _volume_target(MuscleGroup.CHEST, target_sets=10).targets[0],
        minimum_direct_sets=10,
        minimum_effective_sets=10,
        effective_target_sets=10,
        minimum_coverage_required=True,
        direct_minimum_required=True,
    )

    repaired, reasons = repair_weekly_volume(
        (_day(1, existing, focus="upper"),),
        normalized(session_duration_minutes=30),
        WeeklyVolumePlan(targets=(target,), reason_codes=()),
        RULESET,
        candidates=(candidate,),
    )

    assert main_exercise_count(repaired[0].exercises) == 4
    assert all(item.exercise_id != candidate.id for item in repaired[0].exercises)
    assert "VOLUME_REPAIR_HARD_MINIMUM_UNSATISFIED" in reasons


def test_volume_repair_does_not_remove_below_long_session_floor_for_soft_excess() -> None:
    main_exercises = tuple(
        _programmed(f"Existing Chest {index}", MuscleGroup.CHEST, 1) for index in range(5)
    )
    core_exercises = (
        _programmed("Core One", MuscleGroup.ABS, 1, exercise_type=ExerciseType.CORE),
        _programmed("Core Two", MuscleGroup.ABS, 1, exercise_type=ExerciseType.CORE),
    )
    target = replace(
        _volume_target(MuscleGroup.CHEST, target_sets=1).targets[0],
        minimum_soft=0,
        minimum_direct_sets=0,
        minimum_effective_sets=0,
        effective_target_sets=1,
        maximum_hard=10,
    )

    repaired, _reasons = repair_weekly_volume(
        (_day(1, main_exercises + core_exercises, focus="upper"),),
        normalized(session_duration_minutes=45),
        WeeklyVolumePlan(targets=(target,), reason_codes=()),
        RULESET,
    )

    assert main_exercise_count(repaired[0].exercises) == 5


def test_volume_repair_removes_soft_excess_to_short_session_main_floor() -> None:
    existing = tuple(
        _programmed(f"Existing Chest {index}", MuscleGroup.CHEST, 3) for index in range(4)
    )
    target = replace(
        _volume_target(MuscleGroup.CHEST, target_sets=1).targets[0],
        minimum_soft=0,
        maximum_soft=6,
        maximum_hard=20,
        minimum_direct_sets=0,
        minimum_effective_sets=0,
        effective_target_sets=1,
    )

    repaired, _reasons = repair_weekly_volume(
        (_day(1, existing, focus="upper"),),
        normalized(session_duration_minutes=30),
        WeeklyVolumePlan(targets=(target,), reason_codes=()),
        RULESET,
    )

    assert main_exercise_count(repaired[0].exercises) == 3
