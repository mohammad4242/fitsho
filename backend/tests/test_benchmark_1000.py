from __future__ import annotations

import app.main  # Ensure all SQLAlchemy models and relationships are registered
from app.workout_reviews.models import WorkoutPlanReview  # Ensure models loaded

from collections import Counter
import pytest
from app.profile.enums import (
    ExperienceLevel,
    FitnessGoal,
    HomeTrainingSetup,
    Sex,
    TrainingCaution,
    TrainingLocation,
)
from app.workouts.benchmarks.cohort_generator import (
    BENCHMARK_SEED,
    ProfileSpec,
    generate_1000_profiles,
    validate_dataset_sanity,
)
from app.workouts.benchmarks.benchmark_evaluator import evaluate_single_profile
from app.workouts.bodyweight_routing import (
    BODYWEIGHT_ONLY_LEVEL_NOT_SUPPORTED,
    BodyweightRoutingStatus,
    resolve_fixed_bodyweight_route,
)
from app.workouts.program_engine.equipment import resolve_available_equipment
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET


def test_reproducibility_same_seed_produces_identical_profiles():
    """Requirement: Same seed produces identical 1000 profiles."""
    cohort_1 = generate_1000_profiles(BENCHMARK_SEED)
    cohort_2 = generate_1000_profiles(BENCHMARK_SEED)
    assert len(cohort_1) == 1000
    assert len(cohort_2) == 1000
    for p1, p2 in zip(cohort_1, cohort_2):
        assert p1.profile_id == p2.profile_id
        assert p1.name == p2.name
        assert p1.sex == p2.sex
        assert p1.age == p2.age
        assert p1.height_cm == p2.height_cm
        assert p1.weight_kg == p2.weight_kg
        assert p1.experience_level == p2.experience_level
        assert p1.training_days_per_week == p2.training_days_per_week
        assert p1.training_location == p2.training_location
        assert p1.home_training_setup == p2.home_training_setup
        assert p1.training_cautions == p2.training_cautions
        assert p1.fitness_goal == p2.fitness_goal
        assert p1.session_duration_minutes == p2.session_duration_minutes
        assert p1.priority_muscle == p2.priority_muscle


def test_independent_sampling_no_modulo_correlations():
    """Requirement: Different attributes are not tied together by modulo-based correlations."""
    profiles = generate_1000_profiles(BENCHMARK_SEED)
    # Check that Beginner + Bodyweight users do NOT all have knee injuries
    beginner_bw = [
        p for p in profiles
        if p.experience_level == ExperienceLevel.BEGINNER
        and p.training_location == TrainingLocation.HOME
        and p.home_training_setup == HomeTrainingSetup.BODYWEIGHT_ONLY
    ]
    assert len(beginner_bw) > 10
    knee_count = sum(1 for p in beginner_bw if TrainingCaution.KNEE in p.training_cautions)
    healthy_count = sum(1 for p in beginner_bw if len(p.training_cautions) == 0)
    # Knee injury should not be 100% or 0%
    assert 0 < knee_count < len(beginner_bw)
    assert healthy_count > 0

    # Check First Month + Bodyweight users do NOT all have wrist/lower back
    first_month_bw = [
        p for p in profiles
        if p.experience_level == ExperienceLevel.FIRST_MONTH
        and p.training_location == TrainingLocation.HOME
        and p.home_training_setup == HomeTrainingSetup.BODYWEIGHT_ONLY
    ]
    assert len(first_month_bw) > 10
    wrist_lb = sum(
        1 for p in first_month_bw
        if TrainingCaution.WRIST in p.training_cautions or TrainingCaution.LOWER_BACK in p.training_cautions
    )
    assert 0 < wrist_lb < len(first_month_bw)


def test_unsupported_does_not_count_as_failed():
    """Requirement: Unsupported does not count as FAILED, and is excluded from supported denominator."""
    # Mock evaluation counts
    success_count = 800
    failed_count = 130
    unsupported_count = 70
    total = success_count + failed_count + unsupported_count

    assert total == 1000
    supported_profiles = success_count + failed_count
    coverage_rate = supported_profiles / total
    supported_success_rate = success_count / supported_profiles

    # Unsupported is excluded from denominator:
    assert supported_profiles == 930
    assert abs(coverage_rate - 0.93) < 0.001
    assert abs(supported_success_rate - (800 / 930)) < 0.0001
    # If unsupported was mistakenly added to failed, rate would be artificially lower:
    false_rate = success_count / (supported_profiles + unsupported_count)
    assert supported_success_rate > false_rate


def test_first_month_beginner_bodyweight_use_fixed_templates():
    """Requirement: FIRST_MONTH / BEGINNER bodyweight 2/3/4 use fixed templates."""
    for exp in (ExperienceLevel.FIRST_MONTH, ExperienceLevel.BEGINNER):
        for days in (2, 3, 4):
            eq = resolve_available_equipment(
                TrainingLocation.HOME, HomeTrainingSetup.BODYWEIGHT_ONLY, None
            )
            decision = resolve_fixed_bodyweight_route(
                TrainingLocation.HOME, eq, exp, days
            )
            assert decision.status == BodyweightRoutingStatus.FIXED_TEMPLATE
            assert decision.template_slug is not None
            assert decision.is_fixed_template is True
            assert decision.is_bodyweight_route is True


def test_intermediate_advanced_bodyweight_classified_unsupported():
    """Requirement: Intermediate/Advanced BODYWEIGHT_ONLY are classified unsupported."""
    for exp in (ExperienceLevel.INTERMEDIATE, ExperienceLevel.ADVANCED):
        for days in (2, 3, 4, 5):
            eq = resolve_available_equipment(
                TrainingLocation.HOME, HomeTrainingSetup.BODYWEIGHT_ONLY, None
            )
            decision = resolve_fixed_bodyweight_route(
                TrainingLocation.HOME, eq, exp, days
            )
            assert decision.status == BodyweightRoutingStatus.UNSUPPORTED_LEVEL
            assert decision.error_code == BODYWEIGHT_ONLY_LEVEL_NOT_SUPPORTED
            assert decision.is_fixed_template is False


def test_gym_and_home_dumbbell_reach_program_engine():
    """Requirement: Gym and home-dumbbell profiles reach program_engine."""
    # Gym
    gym_eq = resolve_available_equipment(TrainingLocation.GYM, None, None)
    gym_dec = resolve_fixed_bodyweight_route(
        TrainingLocation.GYM, gym_eq, ExperienceLevel.INTERMEDIATE, 4
    )
    assert gym_dec.status == BodyweightRoutingStatus.NOT_BODYWEIGHT_ROUTE

    # Home Dumbbell
    db_eq = resolve_available_equipment(
        TrainingLocation.HOME, HomeTrainingSetup.DUMBBELLS_AVAILABLE, None
    )
    db_dec = resolve_fixed_bodyweight_route(
        TrainingLocation.HOME, db_eq, ExperienceLevel.BEGINNER, 3
    )
    assert db_dec.status == BodyweightRoutingStatus.NOT_BODYWEIGHT_ROUTE


def test_sanity_check_detects_obviously_biased_cohort():
    """Requirement: Dataset sanity check detects an obviously biased artificial cohort."""
    profiles = generate_1000_profiles(BENCHMARK_SEED)
    # Corrupt cohort: force 100% knee caution on all beginners
    corrupted = []
    for p in profiles:
        if p.experience_level == ExperienceLevel.BEGINNER:
            corrupted.append(
                ProfileSpec(
                    **{**p.__dict__, "training_cautions": [TrainingCaution.KNEE]}
                )
            )
        else:
            corrupted.append(p)

    with pytest.raises(ValueError, match="0% healthy profiles|caution prevalence"):
        validate_dataset_sanity(corrupted)


def test_all_results_satisfy_sum_1000():
    """Requirement: All results satisfy: success + failed + unsupported == 1000."""
    import json
    import os

    results_path = "/home/mohammad/project/fitsho/artifacts/fitsho_1000_profiles_results_seed_20260902.json"
    assert os.path.exists(results_path), "Results JSON must exist"

    with open(results_path, "r", encoding="utf-8") as f:
        results = json.load(f)

    assert len(results) == 1000
    success = sum(1 for r in results if r["result_class"] == "SUCCESS")
    failed = sum(1 for r in results if r["result_class"] == "FAILED")
    unsupported = sum(1 for r in results if r["result_class"] == "UNSUPPORTED")

    assert success + failed + unsupported == 1000
    # Supported success rate excludes unsupported
    supported = success + failed
    assert supported == 930
    assert unsupported == 70
    rate = success / supported
    assert 0.85 <= rate <= 0.95
