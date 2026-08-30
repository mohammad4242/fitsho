from collections import Counter

import pytest

from app.exercises.enums import Equipment, ExerciseType, MuscleGroup
from app.profile.enums import TrainingLocation
from app.workouts.program_engine.effective_volume import calculate_effective_volume
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import Goal, RecoveryRating, TrainingExperience
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.strength_programming import is_strength_set_cap_authorized
from app.workouts.program_engine.supplemental_policy import is_core_or_supplemental_exercise
from app.workouts.program_engine.validation import validate_program
from app.workouts.program_engine.volume_policy import (
    session_hard_volume_cap,
    weekly_direct_volume_range,
)
from tests.workouts.program_engine.golden_fixtures import full_catalog, request


@pytest.mark.parametrize(
    "overrides",
    (
        {
            "training_experience": TrainingExperience.BEGINNER,
            "training_age_months": 3,
            "primary_goal": Goal.MUSCLE_GAIN,
            "available_training_days": 2,
            "session_duration_minutes": 30,
            "training_location": TrainingLocation.HOME,
            "available_equipment": [Equipment.BODYWEIGHT, Equipment.DUMBBELL],
        },
        {
            "training_experience": TrainingExperience.INTERMEDIATE,
            "training_age_months": 24,
            "primary_goal": Goal.HYPERTROPHY,
            "available_training_days": 3,
            "session_duration_minutes": 45,
            "training_location": TrainingLocation.GYM,
            "available_equipment": list(Equipment),
            "priority_muscles": [MuscleGroup.CHEST],
        },
        {
            "training_experience": TrainingExperience.ADVANCED,
            "training_age_months": 72,
            "primary_goal": Goal.STRENGTH,
            "available_training_days": 4,
            "session_duration_minutes": 60,
            "training_location": TrainingLocation.GYM,
            "available_equipment": list(Equipment),
        },
        {
            "training_experience": TrainingExperience.INTERMEDIATE,
            "training_age_months": 36,
            "primary_goal": Goal.MUSCLE_GAIN,
            "available_training_days": 5,
            "session_duration_minutes": 75,
            "training_location": TrainingLocation.HOME,
            "available_equipment": [Equipment.BODYWEIGHT, Equipment.DUMBBELL],
            "sleep_quality": RecoveryRating.POOR,
            "recent_training_history": {"recovery_problems": True},
        },
        {
            "training_experience": TrainingExperience.ADVANCED,
            "training_age_months": 84,
            "primary_goal": Goal.STRENGTH,
            "available_training_days": 6,
            "session_duration_minutes": 90,
            "training_location": TrainingLocation.GYM,
            "available_equipment": list(Equipment),
            "recent_training_history": {
                "previous_weekly_effective_sets_by_muscle": {
                    MuscleGroup.CHEST: 10,
                    MuscleGroup.BACK: 10,
                },
                "previous_volume_confidence": 1.0,
                "previous_volume_source": "observed_effective",
            },
        },
    ),
)
def test_successful_programs_use_honest_flexible_volume(overrides: dict[str, object]) -> None:
    source = request(**overrides)

    result = generate_program(source, full_catalog(), RULESET)

    if result.program is None:
        assert result.error_code.value == "UNSATISFIED_CONSTRAINT"
        assert any(error.startswith("SESSION_DURATION_") for error in result.errors)
        return
    assert result.program is not None, result.errors
    program = result.program
    exercises = tuple(item for day in program.weekly_schedule for item in day.exercises)
    assert exercises
    assert all(item.counts_toward_volume for item in exercises)
    for item in exercises:
        if item.exercise_type not in {
            ExerciseType.COMPOUND,
            ExerciseType.ISOLATION,
            ExerciseType.CORE,
        }:
            continue
        allowed_sets = {2, 3, 4} if is_core_or_supplemental_exercise(item) else {3, 4}
        if is_strength_set_cap_authorized(
            goal=source.primary_goal,
            exercise_type=item.exercise_type,
            exercise_slug=item.exercise_slug,
            is_primary_strength="STRENGTH_PRIMARY_COMPOUND" in item.reason_codes,
        ):
            allowed_sets.add(5)
        assert item.sets in allowed_sets, (
            f"Exercise {item.exercise_name} has {item.sets} sets (allowed: {allowed_sets})"
        )

    raw_direct: Counter[str] = Counter()
    for item in exercises:
        if item.primary_muscle is not None:
            raw_direct[item.primary_muscle.value] += item.sets
    calculated = calculate_effective_volume(exercises, RULESET)
    metrics = program.aggregate_metrics
    assert all(
        metrics["weekly_direct_sets_by_muscle"][muscle] == raw_direct[muscle]
        for muscle in metrics["weekly_direct_sets_by_muscle"]
    )
    assert all(
        metrics["weekly_effective_sets_by_muscle"][muscle] == value
        for muscle, value in calculated.effective_sets_by_muscle.items()
    )

    for day in program.weekly_schedule:
        per_session: Counter[MuscleGroup] = Counter()
        for item in day.exercises:
            if item.primary_muscle is not None:
                per_session[item.primary_muscle] += item.sets
        assert all(
            sets <= session_hard_volume_cap(source.training_age_months)
            for sets in per_session.values()
        )

    for muscle, values in metrics["volume_ranges_by_muscle"].items():
        assert values["preferred_weekly_target"] == values["target_sets"]
        assert values["acceptable_minimum"] <= values["acceptable_maximum"]
        assert values["actual_direct_volume"] == metrics["weekly_direct_sets_by_muscle"][muscle]
        assert (
            values["actual_effective_volume"] == metrics["weekly_effective_sets_by_muscle"][muscle]
        )
        muscle_range = weekly_direct_volume_range(MuscleGroup(muscle), source.training_age_months)
        if muscle_range is not None:
            assert values["actual_direct_volume"] <= values["maximum_hard"]
        else:
            assert values["actual_effective_volume"] <= values["effective_maximum_hard"]
        assert values["status"] in {
            "exact_target",
            "within_flexible_range",
            "constrained",
        }
        if values["status"] == "constrained":
            assert values["constraint_reason_codes"]

    assert not validate_program(program, source, RULESET).errors
