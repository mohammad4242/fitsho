from uuid import uuid4

import pytest

from app.exercises.enums import Equipment, MuscleGroup
from app.profile.enums import TrainingLocation
from app.workouts.program_engine.enums import (
    Goal,
    PhysicalJobDemand,
    RecoveryRating,
    SplitType,
    TrainingExperience,
    TrainingStatus,
)
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import (
    NormalizedProgramRequest,
    ProgramGenerationRequest,
    RecentTrainingHistory,
)
from app.workouts.program_engine.split_selector import (
    generate_split_candidates,
    score_split_candidates,
    select_split,
)
from app.workouts.program_engine.volume_planner import (
    SECONDARY_MUSCLES,
    TRACKED_MUSCLES,
    plan_weekly_volume,
)


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


def test_four_days_generate_multiple_valid_split_candidates() -> None:
    candidates = generate_split_candidates(4)
    valid_focuses = {
        "upper",
        "lower",
        "full_body",
        "full_body_b",
        "full_body_c",
        "full_body_d",
        "chest_triceps",
        "back_biceps",
        "legs",
        "shoulders_traps",
    }

    assert tuple(candidate.split_type for candidate in candidates) == (
        SplitType.UPPER_LOWER,
        SplitType.FULL_BODY_FOUR,
        SplitType.UPPER_LOWER_FULL,
        SplitType.PHUL,
        SplitType.BODY_PART_ROTATION,
    )
    assert all(len(candidate.day_focuses) == 4 for candidate in candidates)
    assert all(
        focus in valid_focuses for candidate in candidates for focus in candidate.day_focuses
    )

    scored = score_split_candidates(
        normalized(available_training_days=4),
        candidates,
        RULESET,
        preferred_days=4,
    )
    assert all(len(plan.day_focuses) == len(plan.weekdays) == 4 for plan in scored)
    assert scored == score_split_candidates(
        normalized(available_training_days=4),
        candidates,
        RULESET,
        preferred_days=4,
    )


def test_four_day_recovery_context_can_select_a_lower_complexity_candidate() -> None:
    request = normalized(
        available_training_days=4,
        primary_goal=Goal.HYPERTROPHY,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=30,
        sleep_quality=RecoveryRating.POOR,
    )

    scored = score_split_candidates(
        request,
        generate_split_candidates(4),
        RULESET,
        preferred_days=4,
    )

    assert scored[0].split_type is SplitType.UPPER_LOWER_FULL


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


def test_advanced_user_with_seven_available_days_records_resistance_cap() -> None:
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
    assert "RESISTANCE_DAYS_CAPPED_AT_RULESET_MAXIMUM" in split.reason_codes


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


def test_poor_recovery_user_can_receive_fewer_sessions_than_available() -> None:
    split = select_split(
        normalized(
            available_training_days=6,
            sleep_quality=RecoveryRating.POOR,
        ),
        RULESET,
    )

    assert len(split.day_focuses) < 6
    assert "SPLIT_SELECTED_FOR_APPROPRIATE_SESSION_COUNT" in split.reason_codes


def test_intermediate_four_day_hypertrophy_uses_a_valid_scored_candidate() -> None:
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

    assert split.split_type in {candidate.split_type for candidate in generate_split_candidates(4)}
    assert len(split.day_focuses) == len(split.weekdays) == 4


def test_advanced_four_day_scoring_can_select_body_part_rotation() -> None:
    split = select_split(
        normalized(
            available_training_days=4,
            session_duration_minutes=75,
            primary_goal=Goal.HYPERTROPHY,
            training_experience=TrainingExperience.ADVANCED,
            training_age_months=72,
            recent_training_history=RecentTrainingHistory(consistent_weeks=40),
        ),
        RULESET,
    )

    assert split.split_type is SplitType.BODY_PART_ROTATION
    assert split.split_type in {candidate.split_type for candidate in generate_split_candidates(4)}
    assert len(split.day_focuses) == len(split.weekdays) == 4


def test_five_days_generate_multiple_valid_split_candidates() -> None:
    candidates = generate_split_candidates(5)

    assert tuple(candidate.split_type for candidate in candidates) == (
        SplitType.UPPER_LOWER_SPECIALIZATION,
        SplitType.PUSH_PULL_LEGS_UPPER_LOWER,
        SplitType.BODY_PART_ROTATION,
    )
    assert all(len(candidate.day_focuses) == 5 for candidate in candidates)
    assert all(
        focus
        in {
            "upper",
            "lower",
            "specialization",
            "push",
            "pull",
            "legs",
            "chest_triceps",
            "back_biceps",
            "shoulders_traps",
        }
        for candidate in candidates
        for focus in candidate.day_focuses
    )

    request = normalized(
        available_training_days=5,
        primary_goal=Goal.HYPERTROPHY,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=30,
    )
    scored = score_split_candidates(request, candidates, RULESET, preferred_days=5)
    assert all(len(plan.day_focuses) == len(plan.weekdays) == 5 for plan in scored)
    assert scored == score_split_candidates(request, candidates, RULESET, preferred_days=5)


def test_five_day_context_can_select_specialization_over_body_part_rotation() -> None:
    candidates = generate_split_candidates(5)
    request = normalized(
        available_training_days=5,
        primary_goal=Goal.HYPERTROPHY,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=30,
        priority_muscles=[MuscleGroup.SHOULDERS],
        sleep_quality=RecoveryRating.POOR,
    )

    scored = score_split_candidates(request, candidates, RULESET, preferred_days=5)

    assert scored[0].split_type is SplitType.UPPER_LOWER_SPECIALIZATION
    assert "SPLIT_SELECTED_FOR_PRIORITY_MUSCLE" in scored[0].reason_codes


def test_five_day_context_can_keep_body_part_rotation_when_recovery_is_good() -> None:
    request = normalized(
        available_training_days=5,
        primary_goal=Goal.HYPERTROPHY,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=30,
    )

    scored = score_split_candidates(
        request,
        generate_split_candidates(5),
        RULESET,
        preferred_days=5,
    )

    assert scored[0].split_type is SplitType.BODY_PART_ROTATION


def test_six_days_generate_multiple_valid_split_candidates() -> None:
    candidates = generate_split_candidates(6)

    assert tuple(candidate.split_type for candidate in candidates) == (
        SplitType.PUSH_PULL_LEGS_X2,
        SplitType.UPPER_LOWER_X3,
        SplitType.BODY_PART_ROTATION,
    )
    assert all(len(candidate.day_focuses) == 6 for candidate in candidates)
    assert all(
        focus
        in {
            "push",
            "pull",
            "legs",
            "upper",
            "lower",
            "chest_triceps",
            "back_biceps",
            "quadriceps_calves",
            "shoulders_traps",
            "posterior_chain_core",
            "specialization",
        }
        for candidate in candidates
        for focus in candidate.day_focuses
    )

    request = normalized(
        available_training_days=6,
        primary_goal=Goal.HYPERTROPHY,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=30,
    )
    scored = score_split_candidates(request, candidates, RULESET, preferred_days=6)
    assert all(len(plan.day_focuses) == len(plan.weekdays) == 6 for plan in scored)
    assert scored == score_split_candidates(request, candidates, RULESET, preferred_days=6)


def test_six_day_goal_and_status_context_can_select_upper_lower_x3() -> None:
    request = normalized(
        available_training_days=6,
        primary_goal=Goal.HYPERTROPHY,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=30,
        recent_training_history=RecentTrainingHistory(consistent_weeks=20),
    )

    scored = score_split_candidates(
        request,
        generate_split_candidates(6),
        RULESET,
        preferred_days=6,
    )

    assert scored[0].split_type is SplitType.UPPER_LOWER_X3


def test_six_day_advanced_context_can_select_body_part_rotation() -> None:
    request = normalized(
        available_training_days=6,
        primary_goal=Goal.STRENGTH,
        training_experience=TrainingExperience.ADVANCED,
        training_age_months=72,
    )

    scored = score_split_candidates(
        request,
        generate_split_candidates(6),
        RULESET,
        preferred_days=6,
    )

    assert scored[0].split_type is SplitType.BODY_PART_ROTATION


def test_six_day_recovery_context_penalizes_more_complex_candidates() -> None:
    request = normalized(
        available_training_days=6,
        primary_goal=Goal.HYPERTROPHY,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=30,
    )
    poor_recovery_request = normalized(
        available_training_days=6,
        primary_goal=Goal.HYPERTROPHY,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=30,
        sleep_quality=RecoveryRating.POOR,
    )
    candidates = generate_split_candidates(6)

    good_scores = {
        plan.split_type: plan.score
        for plan in score_split_candidates(request, candidates, RULESET, preferred_days=6)
    }
    poor_scores = {
        plan.split_type: plan.score
        for plan in score_split_candidates(
            poor_recovery_request,
            candidates,
            RULESET,
            preferred_days=6,
        )
    }

    assert poor_scores[SplitType.BODY_PART_ROTATION] < good_scores[SplitType.BODY_PART_ROTATION]
    assert poor_scores[SplitType.BODY_PART_ROTATION] < poor_scores[SplitType.UPPER_LOWER_X3]


def test_six_day_poor_recovery_does_not_promote_advanced_ppl_bonus() -> None:
    request = normalized(
        available_training_days=6,
        primary_goal=Goal.STRENGTH,
        training_experience=TrainingExperience.ADVANCED,
        training_age_months=72,
        recent_training_history=RecentTrainingHistory(consistent_weeks=40),
        sleep_quality=RecoveryRating.POOR,
    )

    scored = score_split_candidates(
        request,
        generate_split_candidates(6),
        RULESET,
        preferred_days=6,
    )

    assert scored[0].split_type is SplitType.UPPER_LOWER_X3


def test_six_day_priority_adds_specialization_context_to_body_part_score() -> None:
    request = normalized(
        available_training_days=6,
        primary_goal=Goal.HYPERTROPHY,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=30,
        priority_muscles=[MuscleGroup.SHOULDERS],
    )

    scored = score_split_candidates(
        request,
        generate_split_candidates(6),
        RULESET,
        preferred_days=6,
    )
    body_part = next(plan for plan in scored if plan.split_type is SplitType.BODY_PART_ROTATION)

    assert "SPLIT_SELECTED_FOR_PRIORITY_MUSCLE" in body_part.reason_codes


def test_goal_specificity_changes_the_score_for_hybrid_candidates() -> None:
    candidate = next(
        item
        for item in generate_split_candidates(5)
        if item.split_type is SplitType.UPPER_LOWER_SPECIALIZATION
    )
    general_request = normalized(available_training_days=5, primary_goal=Goal.GENERAL_FITNESS)
    goal_request = normalized(available_training_days=5, primary_goal=Goal.HYPERTROPHY)

    general_plan = score_split_candidates(
        general_request,
        (candidate,),
        RULESET,
        preferred_days=5,
    )[0]
    goal_plan = score_split_candidates(
        goal_request,
        (candidate,),
        RULESET,
        preferred_days=5,
    )[0]

    assert goal_plan.score > general_plan.score
    assert "SPLIT_SELECTED_FOR_GOAL_SPECIFICITY" in goal_plan.reason_codes


def test_training_status_changes_the_advanced_ppl_score() -> None:
    candidate = next(
        item
        for item in generate_split_candidates(6)
        if item.split_type is SplitType.PUSH_PULL_LEGS_X2
    )
    intermediate_request = normalized(
        available_training_days=6,
        primary_goal=Goal.STRENGTH,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=30,
        recent_training_history=RecentTrainingHistory(consistent_weeks=20),
    )
    advanced_request = normalized(
        available_training_days=6,
        primary_goal=Goal.STRENGTH,
        training_experience=TrainingExperience.ADVANCED,
        training_age_months=72,
        recent_training_history=RecentTrainingHistory(consistent_weeks=40),
    )

    intermediate_plan = score_split_candidates(
        intermediate_request,
        (candidate,),
        RULESET,
        preferred_days=6,
    )[0]
    advanced_plan = score_split_candidates(
        advanced_request,
        (candidate,),
        RULESET,
        preferred_days=6,
    )[0]

    assert advanced_plan.score > intermediate_plan.score
    assert "SPLIT_SELECTED_FOR_ADVANCED_STATUS" in advanced_plan.reason_codes


def test_six_day_program_uses_a_valid_generated_split() -> None:
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

    assert split.split_type in {candidate.split_type for candidate in generate_split_candidates(6)}
    assert len(split.day_focuses) == len(split.weekdays) == 6


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


@pytest.mark.parametrize("muscle", SECONDARY_MUSCLES)
def test_secondary_muscles_receive_explicit_conservative_volume_targets(
    muscle: MuscleGroup,
) -> None:
    request = normalized(primary_goal=Goal.HYPERTROPHY)
    plan = plan_weekly_volume(request, select_split(request, RULESET), RULESET)
    target = next(item for item in plan.targets if item.muscle is muscle)

    assert target.maximum_hard == RULESET.secondary_muscle_maximum_sets[request.training_status]
    assert target.minimum_soft >= RULESET.secondary_muscle_minimum_sets[request.training_status]
    assert target.target_sets <= target.maximum_hard


@pytest.mark.parametrize(
    ("experience", "training_age_months", "goal"),
    [
        (TrainingExperience.BEGINNER, 3, Goal.GENERAL_FITNESS),
        (TrainingExperience.INTERMEDIATE, 30, Goal.HYPERTROPHY),
        (TrainingExperience.ADVANCED, 72, Goal.STRENGTH),
    ],
)
def test_secondary_targets_follow_goal_and_training_status_caps(
    experience: TrainingExperience,
    training_age_months: int,
    goal: Goal,
) -> None:
    request = normalized(
        primary_goal=goal,
        training_experience=experience,
        training_age_months=training_age_months,
    )
    target = next(
        item
        for item in plan_weekly_volume(request, select_split(request, RULESET), RULESET).targets
        if item.muscle is MuscleGroup.TRICEPS
    )
    expected = min(
        max(
            RULESET.secondary_muscle_goal_base_sets[goal],
            RULESET.secondary_muscle_minimum_sets[request.training_status],
        ),
        RULESET.secondary_muscle_maximum_sets[request.training_status],
    )

    assert target.target_sets == expected
    assert target.target_sets <= target.maximum_hard


def test_volume_planner_tracks_all_muscles_and_priority_can_target_biceps() -> None:
    request = normalized(primary_goal=Goal.HYPERTROPHY)
    priority_request = normalized(
        primary_goal=Goal.HYPERTROPHY,
        priority_muscles=[MuscleGroup.BICEPS],
    )
    plan = plan_weekly_volume(request, select_split(request, RULESET), RULESET)
    priority_plan = plan_weekly_volume(
        priority_request,
        select_split(priority_request, RULESET),
        RULESET,
    )

    assert tuple(item.muscle for item in plan.targets) == TRACKED_MUSCLES
    assert priority_plan.direct_sets_for(MuscleGroup.BICEPS) > plan.direct_sets_for(
        MuscleGroup.BICEPS
    )
    assert (
        priority_plan.direct_sets_for(MuscleGroup.BICEPS)
        <= (RULESET.secondary_muscle_maximum_sets[priority_request.training_status])
    )


def test_specialized_four_day_split_caps_volume_to_one_safe_exposure() -> None:
    request = normalized(
        primary_goal=Goal.HYPERTROPHY,
        available_training_days=4,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=30,
        recent_training_history=RecentTrainingHistory(consistent_weeks=20),
    )
    plan = plan_weekly_volume(request, select_split(request, RULESET), RULESET)

    assert plan.direct_sets_for(MuscleGroup.CHEST) <= RULESET.max_sets_per_muscle_per_session
    assert plan.direct_sets_for(MuscleGroup.SHOULDERS) <= RULESET.max_sets_per_muscle_per_session
    assert "VOLUME_CAPPED_FOR_SPLIT_FREQUENCY" in plan.reason_codes


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


def test_history_aware_effective_volume_caps_next_cycle_jump() -> None:
    history = RecentTrainingHistory(
        completed_session_ratio=1.0,
        previous_weekly_direct_sets_by_muscle={MuscleGroup.CHEST: 8.0},
        previous_weekly_effective_sets_by_muscle={MuscleGroup.CHEST: 8.0},
        previous_volume_source="prescribed_plan",
    )
    request = normalized(
        primary_goal=Goal.HYPERTROPHY,
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=30,
        priority_muscles=frozenset({MuscleGroup.CHEST}),
        recent_training_history=history,
    )

    plan = plan_weekly_volume(request, select_split(request, RULESET), RULESET)

    assert plan.effective_target_for(MuscleGroup.CHEST) <= 9
    assert "VOLUME_CAPPED_FOR_PREVIOUS_EFFECTIVE_VOLUME" in plan.reason_codes


def test_low_adherence_does_not_use_full_prescribed_effective_volume_as_baseline() -> None:
    history = RecentTrainingHistory(
        completed_session_ratio=0.25,
        previous_weekly_direct_sets_by_muscle={MuscleGroup.CHEST: 8.0},
        previous_weekly_effective_sets_by_muscle={MuscleGroup.CHEST: 10.0},
        previous_volume_source="prescribed_plan",
    )
    request = normalized(
        primary_goal=Goal.HYPERTROPHY,
        priority_muscles=frozenset({MuscleGroup.CHEST}),
        recent_training_history=history,
    )

    plan = plan_weekly_volume(request, select_split(request, RULESET), RULESET)

    assert plan.effective_target_for(MuscleGroup.CHEST) < 10
    assert "VOLUME_CAPPED_FOR_PREVIOUS_EFFECTIVE_VOLUME" in plan.reason_codes


def test_unknown_history_does_not_reduce_declared_advanced_status() -> None:
    request = normalized(
        training_experience=TrainingExperience.ADVANCED,
        training_age_months=72,
        recent_training_history=RecentTrainingHistory(),
    )

    assert request.training_status is TrainingStatus.ADVANCED


def test_volume_target_exposes_soft_and_hard_boundaries() -> None:
    request = normalized(primary_goal=Goal.HYPERTROPHY)
    target = plan_weekly_volume(request, select_split(request, RULESET), RULESET).targets[0]

    assert target.minimum_soft <= target.target_sets <= target.maximum_soft <= target.maximum_hard
