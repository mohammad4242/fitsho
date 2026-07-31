from uuid import uuid4

from app.exercises.enums import Equipment, MuscleGroup
from app.profile.enums import TrainingLocation
from app.workouts.program_engine.enums import (
    Goal,
    PhysicalJobDemand,
    RecoveryRating,
    SplitType,
    TrainingExperience,
)
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    NormalizedProgramRequest,
    ProgramGenerationRequest,
    RecentTrainingHistory,
)
from app.workouts.program_engine.split_selector import generate_split_candidates, select_split
from app.workouts.program_engine.volume_planner import plan_weekly_volume


def normalized(**overrides: object) -> NormalizedProgramRequest:
    values: dict[str, object] = {
        "user_id": uuid4(),
        "age": 32,
        "height_cm": 175,
        "weight_kg": 76,
        "primary_goal": Goal.GENERAL_FITNESS,
        "training_experience": TrainingExperience.BEGINNER,
        "training_age_months": 3,
        "available_training_days": 3,
        "session_duration_minutes": 45,
        "available_equipment": [Equipment.BODYWEIGHT],
        "training_location": TrainingLocation.HOME,
        "seed_optional": 12,
    }
    values.update(overrides)
    return normalize_request(ProgramGenerationRequest.model_validate(values))


def test_one_day_is_realistic_full_body() -> None:
    split = select_split(normalized(available_training_days=1), RULESET)

    assert split.split_type is SplitType.FULL_BODY
    assert split.day_focuses == ("full_body",)


def test_two_days_use_coherent_full_body_ab_with_spacing() -> None:
    split = select_split(normalized(available_training_days=2), RULESET)

    assert split.split_type is SplitType.FULL_BODY_AB
    assert split.day_focuses == ("full_body_a", "full_body_b")
    assert split.weekdays[1] - split.weekdays[0] >= 3


def test_consecutive_preferred_full_body_days_are_adjusted_for_recovery() -> None:
    split = select_split(
        normalized(available_training_days=3, preferred_weekdays=(0, 1, 2)), RULESET
    )

    assert split.weekdays == RULESET.default_weekdays[3]
    assert "SPLIT_PREFERRED_DAYS_ADJUSTED_FOR_RECOVERY" in split.reason_codes


def test_partial_weekday_preferences_do_not_claim_recovery_adjustment() -> None:
    split = select_split(normalized(available_training_days=3, preferred_weekdays=(0,)), RULESET)

    assert split.weekdays == RULESET.default_weekdays[3]
    assert "SPLIT_PREFERRED_DAYS_ADJUSTED_FOR_RECOVERY" not in split.reason_codes


def test_seven_available_days_never_create_seven_resistance_sessions() -> None:
    split = select_split(
        normalized(
            available_training_days=7,
            training_experience=TrainingExperience.ADVANCED,
            training_age_months=72,
            recent_training_history=RecentTrainingHistory(consistent_weeks=40),
        ),
        RULESET,
    )

    assert len(split.day_focuses) == 6


def test_novice_with_poor_recovery_does_not_receive_high_frequency_split() -> None:
    split = select_split(
        normalized(
            available_training_days=6,
            sleep_quality=RecoveryRating.POOR,
            stress_level=RecoveryRating.POOR,
            physical_job_demand=PhysicalJobDemand.HIGH,
        ),
        RULESET,
    )

    assert len(split.day_focuses) <= 3
    assert "SPLIT_REDUCED_FOR_RECOVERY" in split.reason_codes


def test_intermediate_four_day_hypertrophy_uses_upper_lower_frequency() -> None:
    split = select_split(
        normalized(
            available_training_days=4,
            primary_goal=Goal.HYPERTROPHY,
            training_experience=TrainingExperience.INTERMEDIATE,
            training_age_months=30,
            recent_training_history=RecentTrainingHistory(consistent_weeks=20),
        ),
        RULESET,
    )

    assert split.split_type is SplitType.UPPER_LOWER
    assert split.day_focuses.count("upper") == 2
    assert split.day_focuses.count("lower") == 2


def test_five_days_generate_multiple_valid_split_candidates() -> None:
    candidates = generate_split_candidates(5)

    assert {candidate.split_type for candidate in candidates} == {
        SplitType.UPPER_LOWER_SPECIALIZATION,
        SplitType.PUSH_PULL_LEGS_UPPER_LOWER,
    }


def test_advanced_six_day_strength_selects_specific_ppl_candidate() -> None:
    split = select_split(
        normalized(
            available_training_days=6,
            primary_goal=Goal.STRENGTH,
            training_experience=TrainingExperience.ADVANCED,
            training_age_months=72,
            recent_training_history=RecentTrainingHistory(consistent_weeks=40),
        ),
        RULESET,
    )

    assert split.split_type is SplitType.PUSH_PULL_LEGS_X2
    assert "SPLIT_SELECTED_FOR_GOAL_SPECIFICITY" in split.reason_codes


def test_priority_muscle_receives_more_but_bounded_volume() -> None:
    request = normalized(
        primary_goal=Goal.HYPERTROPHY,
        priority_muscles=[MuscleGroup.SHOULDERS],
    )
    plan = plan_weekly_volume(request, select_split(request, RULESET), RULESET)

    shoulder_sets = plan.direct_sets_for(MuscleGroup.SHOULDERS)
    chest_sets = plan.direct_sets_for(MuscleGroup.CHEST)
    assert shoulder_sets > chest_sets
    assert shoulder_sets <= RULESET.maximum_sets[request.training_status]


def test_poor_recovery_reduces_volume_without_falling_below_novice_floor() -> None:
    request = normalized(
        primary_goal=Goal.HYPERTROPHY,
        sleep_quality=RecoveryRating.POOR,
        stress_level=RecoveryRating.POOR,
    )
    plan = plan_weekly_volume(request, select_split(request, RULESET), RULESET)

    assert plan.direct_sets_for(MuscleGroup.CHEST) == RULESET.minimum_sets[request.training_status]
    assert "VOLUME_REDUCED_FOR_RECOVERY" in plan.reason_codes


def test_previous_volume_caps_unjustified_jump() -> None:
    request = normalized(
        primary_goal=Goal.HYPERTROPHY,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=30,
        recent_training_history=RecentTrainingHistory(
            consistent_weeks=20,
            previous_weekly_sets_by_muscle={MuscleGroup.CHEST: 5},
        ),
    )
    plan = plan_weekly_volume(request, select_split(request, RULESET), RULESET)

    assert plan.direct_sets_for(MuscleGroup.CHEST) <= 6
    assert "VOLUME_CAPPED_FOR_PREVIOUS_VOLUME" in plan.reason_codes
