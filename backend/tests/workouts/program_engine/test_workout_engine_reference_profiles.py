from dataclasses import dataclass
from uuid import UUID, uuid5

import pytest

from app.exercises.enums import Equipment, ExerciseCautionTag, MuscleGroup
from app.profile.enums import TrainingLocation
from app.workouts.program_engine.duration_policy import (
    calculate_main_training_minutes,
    get_session_duration_policy,
)
from app.workouts.program_engine.effective_volume import calculate_effective_volume
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal, SplitType, TrainingExperience
from app.workouts.program_engine.equipment import effective_required_equipment
from app.workouts.program_engine.exercise_semantics import (
    is_primary_working_compound,
    near_equivalent_exercises,
)
from app.workouts.program_engine.recovery import recovery_spacing_is_valid
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.safety import effective_caution_tags
from app.workouts.program_engine.schemas import ProgramGenerationRequest, WorkoutProgram
from app.workouts.program_engine.supplemental_policy import is_supplemental_muscle
from app.workouts.program_engine.validation import validate_program
from app.workouts.program_engine.volume_policy import weekly_direct_volume_range
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


@dataclass(frozen=True)
class ReferenceProfile:
    code: str
    age: int
    height_cm: int
    weight_kg: float
    goal: Goal
    experience: TrainingExperience
    training_age_months: int
    days: int
    location: TrainingLocation
    equipment: tuple[Equipment, ...]
    priorities: tuple[MuscleGroup, ...]
    cautions: tuple[ExerciseCautionTag, ...] = ()
    duration: int = 60
    plan_weeks: int = 4
    seed: int = 20260827


REFERENCE_PROFILES = (
    ReferenceProfile(
        "U1",
        26,
        165,
        62,
        Goal.FAT_LOSS,
        TrainingExperience.BEGINNER,
        4,
        3,
        TrainingLocation.GYM,
        tuple(Equipment),
        (MuscleGroup.GLUTES,),
        (ExerciseCautionTag.DEEP_KNEE_FLEXION,),
        45,
        6,
    ),
    ReferenceProfile(
        "U2",
        34,
        182,
        88,
        Goal.HYPERTROPHY,
        TrainingExperience.INTERMEDIATE,
        30,
        4,
        TrainingLocation.GYM,
        tuple(Equipment),
        (MuscleGroup.CHEST,),
        (),
        60,
        8,
    ),
    ReferenceProfile(
        "U3",
        22,
        158,
        50,
        Goal.GENERAL_FITNESS,
        TrainingExperience.FIRST_MONTH,
        0,
        2,
        TrainingLocation.HOME,
        (Equipment.BODYWEIGHT, Equipment.DUMBBELL),
        (),
        (),
        45,
        4,
    ),
    ReferenceProfile(
        "U4",
        44,
        176,
        84.5,
        Goal.BODY_RECOMPOSITION,
        TrainingExperience.INTERMEDIATE,
        18,
        3,
        TrainingLocation.GYM,
        tuple(Equipment),
        (MuscleGroup.BACK,),
        (ExerciseCautionTag.LOWER_BACK_LOADING, ExerciseCautionTag.SPINAL_FLEXION),
        60,
        6,
    ),
    ReferenceProfile(
        "U5",
        38,
        170,
        67,
        Goal.FAT_LOSS,
        TrainingExperience.BEGINNER,
        2,
        3,
        TrainingLocation.HOME,
        (Equipment.BODYWEIGHT,),
        (MuscleGroup.QUADRICEPS,),
        (ExerciseCautionTag.WRIST_LOADING,),
        45,
        4,
    ),
    ReferenceProfile(
        "U6",
        29,
        188,
        94,
        Goal.STRENGTH,
        TrainingExperience.ADVANCED,
        60,
        5,
        TrainingLocation.GYM,
        tuple(Equipment),
        (MuscleGroup.CHEST,),
        (),
        75,
        8,
    ),
    ReferenceProfile(
        "U7",
        30,
        168,
        59,
        Goal.HYPERTROPHY,
        TrainingExperience.INTERMEDIATE,
        20,
        5,
        TrainingLocation.GYM,
        tuple(Equipment),
        (MuscleGroup.GLUTES,),
        (
            ExerciseCautionTag.OVERHEAD_POSITION,
            ExerciseCautionTag.SHOULDER_INTERNAL_ROTATION,
            ExerciseCautionTag.SHOULDER_EXTERNAL_ROTATION,
        ),
        60,
        6,
    ),
    ReferenceProfile(
        "U8",
        51,
        173,
        79,
        Goal.FAT_LOSS,
        TrainingExperience.BEGINNER,
        3,
        3,
        TrainingLocation.GYM,
        tuple(Equipment),
        (),
        (
            ExerciseCautionTag.NECK_LOADING,
            ExerciseCautionTag.LOWER_BACK_LOADING,
            ExerciseCautionTag.SPINAL_FLEXION,
        ),
        45,
        6,
    ),
    ReferenceProfile(
        "U9",
        24,
        162,
        55.5,
        Goal.BODY_RECOMPOSITION,
        TrainingExperience.ADVANCED,
        48,
        4,
        TrainingLocation.GYM,
        tuple(Equipment),
        (MuscleGroup.GLUTES,),
        (),
        75,
        8,
    ),
    ReferenceProfile(
        "U10",
        20,
        175,
        64,
        Goal.GENERAL_FITNESS,
        TrainingExperience.FIRST_MONTH,
        0,
        3,
        TrainingLocation.HOME,
        (Equipment.BODYWEIGHT, Equipment.DUMBBELL),
        (MuscleGroup.CHEST,),
        (),
        45,
        4,
    ),
)


def _request(profile: ReferenceProfile) -> ProgramGenerationRequest:
    return request(
        user_id=uuid5(UUID("018f0000-0000-7000-8000-000000000000"), profile.code),
        age=profile.age,
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        primary_goal=profile.goal,
        training_experience=profile.experience,
        training_age_months=profile.training_age_months,
        available_training_days=profile.days,
        training_location=profile.location,
        available_equipment=list(profile.equipment),
        priority_muscles=list(profile.priorities),
        blocked_caution_tags=list(profile.cautions),
        session_duration_minutes=profile.duration,
        program_duration_weeks=profile.plan_weeks,
        seed_optional=profile.seed,
    )


def _assert_reference_invariants(
    profile: ReferenceProfile,
    request_value: ProgramGenerationRequest,
    program: WorkoutProgram,
) -> None:
    assert len(program.weekly_schedule) == profile.days
    assert validate_program(program, request_value, RULESET).errors == ()
    assert recovery_spacing_is_valid(program.weekly_schedule, RULESET)

    policy = get_session_duration_policy(profile.duration)
    available = frozenset(profile.equipment)
    effective = calculate_effective_volume(
        (exercise for day in program.weekly_schedule for exercise in day.exercises),
        RULESET,
    ).effective_sets_by_muscle
    ranges = program.aggregate_metrics["volume_ranges_by_muscle"]
    assert isinstance(ranges, dict)
    direct = program.aggregate_metrics["weekly_direct_sets_by_muscle"]
    for muscle, value in effective.items():
        if muscle in ranges:
            muscle_range = weekly_direct_volume_range(
                MuscleGroup(muscle),
                request_value.training_age_months,
            )
            if muscle_range is not None:
                assert direct[muscle] <= ranges[muscle]["maximum_hard"]
            else:
                assert value <= ranges[muscle]["effective_maximum_hard"]

    priority_metrics = program.aggregate_metrics["priority_metrics"]
    assert isinstance(priority_metrics, dict)
    for muscle in profile.priorities:
        if is_supplemental_muscle(muscle):
            continue
        metric = priority_metrics[muscle.value]
        assert metric["direct_sets"] > 0
        assert metric["session_frequency"] > 0
        assert metric["distributed"] is True

    for day in program.weekly_schedule:
        assert day.exercises
        main_training_minutes = calculate_main_training_minutes(day)
        assert policy.contains(main_training_minutes)
        for first_index, first in enumerate(day.exercises):
            assert first.is_active and first.is_programmable and not first.needs_review
            assert effective_required_equipment(first.equipment, first.movement_pattern).issubset(
                available
            )
            assert not effective_caution_tags(first).intersection(
                request_value.blocked_caution_tags
            )
            assert "HARD_INCOMPATIBLE" not in first.reason_codes
            assert "RECOVERED_INCOMPATIBLE_SEMANTICS" not in first.reason_codes
            for second in day.exercises[first_index + 1 :]:
                assert not near_equivalent_exercises(first, second)

        working_compounds = [
            index
            for index, exercise in enumerate(day.exercises)
            if is_primary_working_compound(exercise)
        ]
        if working_compounds:
            assert working_compounds[0] <= max(1, len(day.exercises) // 2)


@pytest.mark.parametrize("profile", REFERENCE_PROFILES, ids=lambda item: item.code)
def test_reference_profiles_preserve_safety_quality_and_determinism(
    profile: ReferenceProfile,
) -> None:
    request_value = _request(profile)
    catalog = full_catalog()
    result = generate_program(request_value, catalog, RULESET)

    if not result.is_success:
        assert result.error_code.value == "UNSATISFIED_CONSTRAINT"
        assert any(error.startswith("SESSION_DURATION_") for error in result.errors)
        return
    assert result.is_success, f"{profile.code}: {result.errors}"
    assert result.program is not None
    _assert_reference_invariants(profile, request_value, result.program)

    reversed_result = generate_program(request_value, list(reversed(catalog)), RULESET)
    assert reversed_result.is_success
    assert reversed_result.program == result.program

    if profile.code == "U2":
        assert result.program.split.split_type is SplitType.BODY_PART_ROTATION
        assert "PROFESSIONAL_TOPOLOGY_BODY_PART_PREFERENCE" in result.program.split.reason_codes

    print(
        f"PROFILE {profile.code} PASS days={len(result.program.weekly_schedule)} "
        f"split={result.program.split.split_type.value} "
        f"warnings={len(result.program.validation_report.warnings)}"
    )
