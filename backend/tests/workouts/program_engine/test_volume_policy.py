from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.enums import (
    Goal,
    PhysicalJobDemand,
    RecoveryRating,
    SplitType,
    TrainingExperience,
)
from app.workouts.program_engine.normalization import normalize_request
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import RecentTrainingHistory, SplitPlan
from app.workouts.program_engine.volume_planner import plan_weekly_volume
from tests.workouts.program_engine.golden_fixtures import request

FULL_BODY = SplitPlan(
    split_type=SplitType.FULL_BODY_ABC,
    day_focuses=("full_body_a", "full_body_b", "full_body_c"),
    weekdays=(0, 2, 4),
    score=0,
    reason_codes=(),
)


def _plan(**overrides: object):
    values: dict[str, object] = {
        "primary_goal": Goal.HYPERTROPHY,
        "training_experience": TrainingExperience.INTERMEDIATE,
        "training_age_months": 30,
        "available_training_days": 3,
    }
    values.update(overrides)
    source = request(**values)
    normalized = normalize_request(source, RULESET)
    return normalized, plan_weekly_volume(normalized, FULL_BODY, RULESET)


def test_muscle_specific_profiles_produce_different_preferred_targets() -> None:
    _, plan = _plan()

    assert plan.direct_sets_for(MuscleGroup.BACK) > plan.direct_sets_for(MuscleGroup.ABS)
    assert plan.direct_sets_for(MuscleGroup.CHEST) > plan.direct_sets_for(MuscleGroup.CALVES)
    assert plan.direct_sets_for(MuscleGroup.BICEPS) > plan.direct_sets_for(MuscleGroup.FOREARMS)


def test_muscle_targets_remain_inside_global_hard_boundaries() -> None:
    normalized, plan = _plan(
        training_experience=TrainingExperience.ADVANCED,
        training_age_months=72,
    )

    for target in plan.targets:
        hard_maximum = (
            RULESET.secondary_muscle_maximum_sets[normalized.training_status]
            if target.muscle
            in {
                MuscleGroup.BICEPS,
                MuscleGroup.TRICEPS,
                MuscleGroup.TRAPS,
                MuscleGroup.FOREARMS,
            }
            else RULESET.maximum_sets[normalized.training_status]
        )
        assert target.target_sets <= hard_maximum
        assert target.maximum_hard <= hard_maximum


def test_volume_flexibility_changes_with_personalized_target_size() -> None:
    _, novice = _plan(
        primary_goal=Goal.GENERAL_FITNESS,
        training_experience=TrainingExperience.BEGINNER,
        training_age_months=3,
    )
    _, intermediate = _plan()
    _, advanced = _plan(
        training_experience=TrainingExperience.ADVANCED,
        training_age_months=72,
    )

    novice_triceps = next(
        target for target in novice.targets if target.muscle is MuscleGroup.TRICEPS
    )
    intermediate_chest = next(
        target for target in intermediate.targets if target.muscle is MuscleGroup.CHEST
    )
    advanced_back = next(target for target in advanced.targets if target.muscle is MuscleGroup.BACK)

    assert novice_triceps.maximum_soft - novice_triceps.target_sets == 1
    assert intermediate_chest.target_sets - intermediate_chest.minimum_soft == 2
    assert advanced_back.target_sets - advanced_back.minimum_soft == 3


def test_previous_volume_twenty_percent_limit_is_default_soft_cap() -> None:
    history = RecentTrainingHistory(
        completed_session_ratio=0.7,
        previous_weekly_effective_sets_by_muscle={MuscleGroup.CHEST: 8.0},
        previous_volume_confidence=1.0,
        previous_volume_source="observed_effective",
    )
    _, plan = _plan(recent_training_history=history)

    assert plan.effective_target_for(MuscleGroup.CHEST) == 9
    assert "VOLUME_CAPPED_FOR_PREVIOUS_EFFECTIVE_VOLUME" in plan.reason_codes


def test_reliable_positive_history_can_override_previous_volume_soft_cap() -> None:
    history = RecentTrainingHistory(
        completed_session_ratio=0.95,
        previous_weekly_effective_sets_by_muscle={MuscleGroup.CHEST: 8.0},
        previous_volume_confidence=0.95,
        previous_volume_source="observed_effective",
        performance_trend="stable",
        recovery_problems=False,
    )
    _, plan = _plan(recent_training_history=history)

    assert plan.effective_target_for(MuscleGroup.CHEST) == 10
    assert "PREVIOUS_VOLUME_SOFT_CAP_OVERRIDDEN_WITH_POSITIVE_HISTORY" in plan.reason_codes


def test_recovery_signals_form_a_bounded_burden_instead_of_additive_penalties() -> None:
    _, normal = _plan(
        training_experience=TrainingExperience.ADVANCED,
        training_age_months=72,
    )
    _, moderate = _plan(
        training_experience=TrainingExperience.ADVANCED,
        training_age_months=72,
        sleep_quality=RecoveryRating.POOR,
    )
    _, strong = _plan(
        training_experience=TrainingExperience.ADVANCED,
        training_age_months=72,
        sleep_quality=RecoveryRating.POOR,
        stress_level=RecoveryRating.POOR,
        physical_job_demand=PhysicalJobDemand.HIGH,
        recent_training_history=RecentTrainingHistory(recovery_problems=True),
    )

    normal_back = normal.direct_sets_for(MuscleGroup.BACK)
    moderate_back = moderate.direct_sets_for(MuscleGroup.BACK)
    strong_back = strong.direct_sets_for(MuscleGroup.BACK)
    assert normal_back > moderate_back >= strong_back
    assert normal_back - strong_back <= 3
    assert "RECOVERY_BURDEN_MODERATE" in moderate.reason_codes
    assert "RECOVERY_BURDEN_STRONG" in strong.reason_codes


def test_secondary_set_credit_remains_one_half() -> None:
    _, plan = _plan()

    chest = next(target for target in plan.targets if target.muscle is MuscleGroup.CHEST)
    assert chest.fractional_sets == chest.target_sets * 0.5
