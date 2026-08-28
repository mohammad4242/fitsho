from dataclasses import replace

import pytest

from app.exercises.enums import Equipment, ExerciseCautionTag, MovementPattern, MuscleGroup
from app.workouts.program_engine.duration_policy import get_session_duration_policy
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import GenerationErrorCode, SafetyStatus, SplitType
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.validation import validate_program
from app.workouts.program_engine.volume_planner import PLANNED_MUSCLES, TRACKED_MUSCLES
from tests.workouts.program_engine.golden_fixtures import (
    exercise,
    full_catalog,
    golden_scenarios,
    impossible_equipment_request,
    request,
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
    policy = get_session_duration_policy(source.session_duration_minutes)
    assert all(
        policy.workout_minutes(
            day.estimated_duration_minutes
            - (day.cardio.duration_minutes if getattr(day, "cardio", None) else 0),
            RULESET.general_warmup_minutes,
        )
        <= policy.maximum_minutes
        for day in result.program.weekly_schedule
    )
    if any(
        policy.workout_minutes(
            day.estimated_duration_minutes
            - (day.cardio.duration_minutes if getattr(day, "cardio", None) else 0),
            RULESET.general_warmup_minutes,
        )
        < policy.minimum_minutes
        for day in result.program.weekly_schedule
    ):
        duration_trace = next(
            entry for entry in result.program.decision_trace if entry["stage"] == "session_duration"
        )
        assert {
            "SESSION_DURATION_CONSTRAINED_BY_HARD_VOLUME_LIMITS",
            "SESSION_DURATION_TARGET_SATISFIED",
        }.intersection(duration_trace["reason_codes"])
        assert all(
            len(day.exercises) >= 2 and all(item.counts_toward_volume for item in day.exercises)
            for day in result.program.weekly_schedule
        )


@pytest.mark.parametrize("requested_days", [2, 3, 4, 5])
def test_successful_generation_preserves_requested_training_days(requested_days: int) -> None:
    source = request(
        available_training_days=requested_days,
        training_experience="intermediate",
        training_age_months=24,
    )

    catalog = full_catalog()
    if requested_days == 6:
        catalog.append(exercise("seated-calf", MovementPattern.CALF_RAISE, MuscleGroup.CALVES))
    result = generate_program(source, catalog, RULESET)

    assert result.program is not None, result.errors
    assert len(result.program.weekly_schedule) == requested_days
    assert len(result.program.split.day_focuses) == requested_days
    assert all(day.exercises for day in result.program.weekly_schedule)


def test_six_day_generation_succeeds_with_scaled_frequency_caps() -> None:
    source = request(
        available_training_days=6,
        training_experience="intermediate",
        training_age_months=24,
    )
    catalog = full_catalog()
    catalog.append(exercise("seated-calf", MovementPattern.CALF_RAISE, MuscleGroup.CALVES))

    result = generate_program(source, catalog, RULESET)

    assert result.is_success
    assert len(result.program.weekly_schedule) == 6


def test_preferred_weekdays_are_preserved_for_exact_day_generation() -> None:
    source = request(
        available_training_days=3,
        preferred_weekdays=(0, 2, 4),
        training_experience="intermediate",
        training_age_months=24,
    )

    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None, result.errors
    assert tuple(day.weekday for day in result.program.weekly_schedule) == (0, 2, 4)


def test_exact_day_construction_failure_does_not_return_shorter_success() -> None:
    source = request(
        available_training_days=5,
        training_experience="intermediate",
        training_age_months=24,
    )
    catalog = [item for item in full_catalog() if item.primary_muscle is MuscleGroup.CHEST]

    result = generate_program(source, catalog, RULESET)

    assert result.program is None
    assert result.error_code is GenerationErrorCode.UNSATISFIED_CONSTRAINT
    assert "REQUESTED_TRAINING_DAYS_UNSATISFIED" in result.errors
    assert "EXACT_DAY_SPLIT_ALTERNATIVES_EXHAUSTED" in result.errors


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
        assert len(result.program.weekly_schedule) == source.available_training_days
        assert "VOLUME_REDUCED_FOR_RECOVERY" in next(
            entry["reasons"]
            for entry in result.program.decision_trace
            if entry["stage"] == "volume"
        )
    if name == "short_25_minutes":
        exercise_count_satisfied = all(
            RULESET.minimum_exercises_per_session
            <= len(day.exercises)
            <= RULESET.max_exercises_per_session
            for day in result.program.weekly_schedule
        )
        if not exercise_count_satisfied:
            assert "DURATION_PLANNED_REDUCED_EXERCISE_COUNT" in result.program.warnings
        assert all(
            source.session_duration_minutes - 10
            <= (
                day.estimated_duration_minutes
                - RULESET.general_warmup_minutes
                - (day.cardio.duration_minutes if getattr(day, "cardio", None) else 0)
            )
            <= source.session_duration_minutes + 10
            for day in result.program.weekly_schedule
        )
        assert all(
            item.counts_toward_volume
            for day in result.program.weekly_schedule
            for item in day.exercises
        )


def test_generate_program_excludes_metadata_unsafe_wrist_exercises() -> None:
    source = request(blocked_caution_tags=[ExerciseCautionTag.WRIST_LOADING])
    catalog = full_catalog()
    bodyweight_press_ids = {
        item.id
        for item in catalog
        if item.movement_pattern is MovementPattern.HORIZONTAL_PUSH
        and Equipment.BODYWEIGHT in item.equipment
    }

    result = generate_program(source, catalog, RULESET)

    assert result.program is not None, result.errors
    selected_ids = {
        item.exercise_id for day in result.program.weekly_schedule for item in day.exercises
    }
    assert bodyweight_press_ids.isdisjoint(selected_ids)


def test_generate_program_home_excludes_bodyweight_pull_up_without_bar_metadata() -> None:
    source = request(available_equipment=[Equipment.BODYWEIGHT])
    pull_up = next(item for item in full_catalog() if item.name == "Chin Up")

    result = generate_program(source, [pull_up, *full_catalog()], RULESET)

    assert result.program is not None, result.errors
    selected_ids = {
        item.exercise_id for day in result.program.weekly_schedule for item in day.exercises
    }
    assert pull_up.id not in selected_ids


def test_final_validation_rejects_metadata_unsafe_programmed_exercise() -> None:
    source = request(blocked_caution_tags=[ExerciseCautionTag.WRIST_LOADING])
    result = generate_program(request(), full_catalog(), RULESET)
    assert result.program is not None, result.errors
    target_day = next(
        day
        for day in result.program.weekly_schedule
        if any(
            item.movement_pattern is MovementPattern.HORIZONTAL_PUSH
            and Equipment.BODYWEIGHT in item.equipment
            for item in day.exercises
        )
    )
    tampered_days = tuple(
        replace(
            day,
            exercises=tuple(
                replace(item, caution_tags=frozenset())
                if day is target_day
                and item.movement_pattern is MovementPattern.HORIZONTAL_PUSH
                and Equipment.BODYWEIGHT in item.equipment
                else item
                for item in day.exercises
            ),
        )
        for day in result.program.weekly_schedule
    )
    tampered_program = replace(result.program, weekly_schedule=tampered_days)

    report = validate_program(tampered_program, source, RULESET)

    assert "BLOCKED_CAUTION_TAG_SELECTED" in report.errors


def test_final_validation_rejects_vertical_pull_without_pull_up_bar() -> None:
    source = request(available_equipment=[Equipment.BODYWEIGHT])
    result = generate_program(source, full_catalog(), RULESET)
    assert result.program is not None, result.errors
    target_day = result.program.weekly_schedule[0]
    target = target_day.exercises[0]
    tampered_day = replace(
        target_day,
        exercises=(
            replace(
                target,
                movement_pattern=MovementPattern.VERTICAL_PULL,
                equipment=frozenset({Equipment.BODYWEIGHT}),
            ),
            *target_day.exercises[1:],
        ),
    )
    tampered_program = replace(
        result.program,
        weekly_schedule=(tampered_day, *result.program.weekly_schedule[1:]),
    )

    report = validate_program(tampered_program, source, RULESET)

    assert "UNAVAILABLE_EQUIPMENT_SELECTED" in report.errors


def test_priority_muscle_affects_volume_without_overriding_session_structure() -> None:
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
    assert all(
        tuple(item.order for item in day.exercises) == tuple(range(1, len(day.exercises) + 1))
        for day in shoulder_days
    )


def test_aggregate_volume_metrics_expose_every_tracked_muscle() -> None:
    source = golden_scenarios()["intermediate_5_days_shoulder_priority"]
    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None, result.errors
    planned = result.program.aggregate_metrics["planned_direct_sets_by_muscle"]
    weekly = result.program.aggregate_metrics["weekly_direct_sets_by_muscle"]

    assert all(muscle.value in planned for muscle in PLANNED_MUSCLES)
    assert all(
        muscle.value not in planned for muscle in set(TRACKED_MUSCLES) - set(PLANNED_MUSCLES)
    )
    assert all(muscle.value in weekly for muscle in TRACKED_MUSCLES)


def test_aggregate_volume_metrics_expose_effective_secondary_credit() -> None:
    source = golden_scenarios()["intermediate_5_days_shoulder_priority"]
    result = generate_program(source, full_catalog(), RULESET)

    assert result.program is not None, result.errors
    metrics = result.program.aggregate_metrics
    direct = metrics["weekly_direct_sets_by_muscle"]
    secondary = metrics["weekly_fractional_sets_by_muscle"]
    effective = metrics["weekly_effective_sets_by_muscle"]

    assert effective[MuscleGroup.TRICEPS.value] == pytest.approx(
        direct[MuscleGroup.TRICEPS.value] + secondary[MuscleGroup.TRICEPS.value]
    )
    assert effective[MuscleGroup.TRICEPS.value] > 0


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
    volume_trace = next(
        entry for entry in result.program.decision_trace if entry["stage"] == "volume"
    )
    repair_trace = next(
        entry for entry in result.program.decision_trace if entry["stage"] == "volume_repair"
    )
    assert "effective_targets" in volume_trace
    assert "weekly_effective_sets" in repair_trace
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


def test_niloofar_profile_recovers_from_an_undersized_body_part_session() -> None:
    source = request(
        biological_sex_optional="female",
        primary_goal="build_muscle",
        training_experience="intermediate",
        training_age_months=30,
        available_training_days=4,
        session_duration_minutes=60,
        available_equipment=[Equipment.BODYWEIGHT, Equipment.DUMBBELL],
        priority_muscles=[MuscleGroup.GLUTES],
    )
    catalog = [item for item in full_catalog() if item.name != "Isometric Shrug"]

    first = generate_program(source, catalog, RULESET)
    second = generate_program(source, list(reversed(catalog)), RULESET)

    assert first.program is not None, first.errors
    assert second.program == first.program
    assert first.program.validation_report.is_valid
    assert all(
        RULESET.minimum_exercises_per_session
        <= len(day.exercises)
        <= RULESET.max_exercises_per_session
        for day in first.program.weekly_schedule
    )
    duration_policy = get_session_duration_policy(source.session_duration_minutes)
    assert all(
        day.estimated_duration_minutes
        <= duration_policy.maximum_total_minutes(RULESET.general_warmup_minutes)
        for day in first.program.weekly_schedule
    )
    selected = [item for day in first.program.weekly_schedule for item in day.exercises]
    assert all(item.equipment.issubset(source.available_equipment) for item in selected)
    assert all(
        item.is_active and item.is_programmable and not item.needs_review for item in selected
    )
    recovery = next(
        entry for entry in first.program.decision_trace if entry["stage"] == "construction_recovery"
    )
    assert {
        "SESSION_DURATION_REPAIR_APPLIED",
        "SESSION_DURATION_CONSTRAINED_BY_HARD_VOLUME_LIMITS",
        "SESSION_DURATION_TARGET_SATISFIED",
    }.intersection(recovery["reason_codes"])
    priority_metrics = first.program.aggregate_metrics["priority_metrics"]
    assert priority_metrics[MuscleGroup.GLUTES.value]["session_frequency"] >= 2


def test_generation_exhausts_safe_splits_when_required_pull_is_unavailable() -> None:
    source = request(
        primary_goal="build_muscle",
        training_experience="intermediate",
        training_age_months=30,
        available_training_days=4,
        session_duration_minutes=60,
    )
    catalog = [
        item
        for item in full_catalog()
        if item.movement_pattern
        not in {MovementPattern.HORIZONTAL_PULL, MovementPattern.VERTICAL_PULL}
    ]

    result = generate_program(source, catalog, RULESET)

    assert result.program is None
    assert result.error_code is GenerationErrorCode.UNSATISFIED_CONSTRAINT
    assert result.errors[0] == "PROGRAM_CONSTRUCTION_ALTERNATIVES_EXHAUSTED"
    assert "SESSION_CONSTRUCTION_FAILED_REQUIRED_SLOT" in result.errors
    assert any(error.startswith("REQUIRED_PATTERN_UNAVAILABLE:") for error in result.errors)
    assert result.decision_trace[-1]["status"] == "exhausted"


def test_priority_selection_prefers_a_fillable_split_with_distributed_exposure() -> None:
    source = request(
        primary_goal="build_muscle",
        training_experience="intermediate",
        training_age_months=30,
        available_training_days=4,
        session_duration_minutes=60,
        priority_muscles=[MuscleGroup.GLUTES],
    )
    catalog = [
        item
        for item in full_catalog()
        if item.primary_muscle not in {MuscleGroup.SHOULDERS, MuscleGroup.TRAPS}
    ]

    result = generate_program(source, catalog, RULESET)

    assert result.program is not None, result.errors
    assert result.program.split.split_type is SplitType.UPPER_LOWER
    priority_metrics = result.program.aggregate_metrics["priority_metrics"]
    assert priority_metrics[MuscleGroup.GLUTES.value]["session_frequency"] >= 2
