import pytest

from app.exercises.enums import Equipment, MovementPattern, MuscleGroup
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import GenerationErrorCode, SafetyStatus, SplitType
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.volume_planner import TRACKED_MUSCLES
from tests.workouts.program_engine.golden_fixtures import (
    full_catalog,
    golden_scenarios,
    impossible_equipment_request,
)

FOUR_DAY_SPLIT_TYPES = frozenset(
    {
        SplitType.UPPER_LOWER,
        SplitType.FULL_BODY_FOUR,
        SplitType.UPPER_LOWER_FULL,
        SplitType.PHUL,
        SplitType.BODY_PART_ROTATION,
    }
)
FIVE_DAY_SPLIT_TYPES = frozenset(
    {
        SplitType.UPPER_LOWER_SPECIALIZATION,
        SplitType.PUSH_PULL_LEGS_UPPER_LOWER,
        SplitType.BODY_PART_ROTATION,
    }
)


@pytest.mark.parametrize(
    ("name", "split_type"),
    [
        ("novice_1_day_45_general", SplitType.FULL_BODY),
        ("novice_2_days_35_general", SplitType.FULL_BODY_AB),
        ("novice_3_days_fat_loss_low_impact", SplitType.FULL_BODY_ABC),
        ("intermediate_4_days_hypertrophy", None),
        ("intermediate_5_days_shoulder_priority", None),
        ("advanced_4_days_strength", None),
    ],
)
def test_golden_split_and_validation(name: str, split_type: SplitType | None) -> None:
    source = golden_scenarios()[name]
    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None, result.errors
    if split_type is not None:
        assert result.program.split.split_type is split_type
    if source.available_training_days == 4:
        assert result.program.split.split_type in FOUR_DAY_SPLIT_TYPES
    if source.available_training_days == 5:
        assert result.program.split.split_type in FIVE_DAY_SPLIT_TYPES
    assert result.program.validation_report.is_valid
    assert all(
        day.estimated_duration_minutes
        <= source.session_duration_minutes + RULESET.duration_tolerance_minutes
        for day in result.program.weekly_schedule
    )


@pytest.mark.parametrize(
    "name",
    [
        "home_dumbbells_only",
        "bodyweight_only",
        "no_overhead",
        "limited_knee_flexion",
        "no_spinal_flexion",
        "high_job_poor_recovery",
        "short_25_minutes",
    ],
)
def test_golden_constraints_and_recovery(name: str) -> None:
    source = golden_scenarios()[name]
    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None, result.errors
    selected = [item for day in result.program.weekly_schedule for item in day.exercises]
    assert all(item.equipment.issubset(source.available_equipment) for item in selected)
    assert all(item.movement_pattern not in source.blocked_movement_patterns for item in selected)
    assert all(not item.caution_tags.intersection(source.blocked_caution_tags) for item in selected)
    assert all(not item.needs_review for item in selected)
    if name == "no_overhead":
        assert all(item.movement_pattern is not MovementPattern.VERTICAL_PUSH for item in selected)
    if name == "limited_knee_flexion":
        assert any(item.movement_pattern is MovementPattern.KNEE_EXTENSION for item in selected)
    if name == "no_spinal_flexion":
        assert all(item.movement_pattern is not MovementPattern.SPINAL_FLEXION for item in selected)
    if name == "high_job_poor_recovery":
        assert len(result.program.weekly_schedule) <= 3
        assert "VOLUME_REDUCED_FOR_RECOVERY" in next(
            entry["reasons"]
            for entry in result.program.decision_trace
            if entry["stage"] == "volume"
        )
    if name == "short_25_minutes":
        assert all(
            RULESET.minimum_exercises_per_session
            <= len(day.exercises)
            <= RULESET.max_exercises_per_session
            for day in result.program.weekly_schedule
        )


def test_priority_muscle_affects_volume_and_order() -> None:
    source = golden_scenarios()["intermediate_5_days_shoulder_priority"]
    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None, result.errors
    planned = result.program.aggregate_metrics["planned_direct_sets_by_muscle"]
    assert planned[MuscleGroup.SHOULDERS.value] > planned[MuscleGroup.CHEST.value]
    shoulder_days = [
        day
        for day in result.program.weekly_schedule
        if any(item.primary_muscle is MuscleGroup.SHOULDERS for item in day.exercises)
    ]
    assert shoulder_days
    assert all(day.exercises[0].primary_muscle is MuscleGroup.SHOULDERS for day in shoulder_days)


def test_aggregate_volume_metrics_expose_every_tracked_muscle() -> None:
    source = golden_scenarios()["intermediate_5_days_shoulder_priority"]
    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None, result.errors
    planned = result.program.aggregate_metrics["planned_direct_sets_by_muscle"]
    weekly = result.program.aggregate_metrics["weekly_direct_sets_by_muscle"]

    assert all(muscle.value in planned for muscle in TRACKED_MUSCLES)
    assert all(muscle.value in weekly for muscle in TRACKED_MUSCLES)


def test_four_day_program_uses_a_valid_generated_focus_for_each_day() -> None:
    result = generate_program(
        golden_scenarios()["intermediate_4_days_hypertrophy"], full_catalog(), RULESET
    )

    assert result.program is not None, result.errors
    assert result.program.split.split_type in FOUR_DAY_SPLIT_TYPES
    assert len(result.program.weekly_schedule) == 4
    assert tuple(day.focus for day in result.program.weekly_schedule) == (
        result.program.split.day_focuses
    )


def test_program_trace_explains_priority_volume_and_repair_boundary() -> None:
    result = generate_program(
        golden_scenarios()["intermediate_5_days_shoulder_priority"], full_catalog(), RULESET
    )

    assert result.program is not None, result.errors
    stages = {entry["stage"] for entry in result.program.decision_trace}
    assert {"split", "volume", "volume_repair"}.issubset(stages)
    ranges = result.program.aggregate_metrics["volume_ranges_by_muscle"]
    assert (
        ranges[MuscleGroup.SHOULDERS.value]["target_sets"]
        > ranges[MuscleGroup.CHEST.value]["target_sets"]
    )


def test_low_impact_scenario_never_uses_high_impact_cardio() -> None:
    source = golden_scenarios()["novice_3_days_fat_loss_low_impact"]
    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None, result.errors
    selected_cardio_names = {
        day.cardio.modality_name for day in result.program.weekly_schedule if day.cardio
    }
    assert "Jumping Jacks" not in selected_cardio_names


def test_impossible_equipment_combination_is_structured_failure() -> None:
    source, catalog = impossible_equipment_request()
    result = generate_program(source, catalog, RULESET)

    assert result.program is None
    assert result.error_code is GenerationErrorCode.NO_AVAILABLE_EQUIPMENT_MATCH


def test_red_flag_is_not_programmed() -> None:
    source = golden_scenarios()["safety_red_flag"]
    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is None
    assert result.safety_status is SafetyStatus.STOP_AND_REFER


def test_bodyweight_program_does_not_select_dumbbells() -> None:
    source = golden_scenarios()["bodyweight_only"]
    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None
    assert all(
        Equipment.DUMBBELL not in item.equipment
        for day in result.program.weekly_schedule
        for item in day.exercises
    )
