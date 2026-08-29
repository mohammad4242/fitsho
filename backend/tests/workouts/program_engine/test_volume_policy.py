import pytest

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
from app.workouts.program_engine.volume_policy import (
    LARGE_MUSCLES,
    SMALL_MUSCLES,
    session_direct_volume_range,
    session_hard_volume_cap,
    weekly_direct_volume_range,
)
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

    from app.workouts.program_engine.volume_policy import weekly_direct_volume_range

    for target in plan.targets:
        range_limit = weekly_direct_volume_range(
            target.muscle, normalized.source.training_age_months
        )
        if range_limit:
            assert target.target_sets <= range_limit.maximum
            assert target.maximum_hard <= range_limit.maximum
        else:
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
    assert intermediate_chest.target_sets - intermediate_chest.minimum_soft == 0
    assert advanced_back.maximum_soft - advanced_back.target_sets == 3


def test_previous_volume_twenty_percent_limit_is_default_soft_cap() -> None:
    history = RecentTrainingHistory(
        completed_session_ratio=0.7,
        previous_weekly_effective_sets_by_muscle={MuscleGroup.CHEST: 8.0},
        previous_volume_confidence=1.0,
        previous_volume_source="observed_effective",
    )
    _, plan = _plan(recent_training_history=history)

    assert plan.effective_target_for(MuscleGroup.CHEST) >= 8


def test_reliable_positive_history_can_override_previous_volume_soft_cap() -> None:
    history = RecentTrainingHistory(
        completed_session_ratio=0.95,
        previous_weekly_effective_sets_by_muscle={MuscleGroup.CHEST: 8.0},
        previous_volume_confidence=0.95,
        previous_volume_source="observed_effective",
        performance_trend="stable",
        recovery_problems=False,
    )
    _, plan = _plan(
        training_experience=TrainingExperience.INTERMEDIATE,
        training_age_months=12,
        recent_training_history=history,
    )

    assert plan.effective_target_for(MuscleGroup.CHEST) == 10


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


def test_session_hard_volume_cap_boundaries():
    # Beginner: < 6 -> 12
    assert session_hard_volume_cap(0) == 12
    assert session_hard_volume_cap(5) == 12

    # Intermediate: 6..24 -> 20
    assert session_hard_volume_cap(6) == 20
    assert session_hard_volume_cap(24) == 20

    # Advanced: > 24 -> 30
    assert session_hard_volume_cap(25) == 30
    assert session_hard_volume_cap(60) == 30


@pytest.mark.parametrize(
    ("months", "large_range", "small_range"),
    [
        (0, (6, 10), (4, 6)),
        (5, (6, 10), (4, 6)),
        (6, (10, 24), (6, 20)),
        (24, (10, 24), (6, 20)),
        (25, (12, 30), (8, 20)),
        (60, (12, 30), (8, 20)),
    ],
)
def test_weekly_direct_volume_range_boundaries(
    months: int,
    large_range: tuple[int, int],
    small_range: tuple[int, int],
) -> None:
    for muscle in LARGE_MUSCLES:
        assert weekly_direct_volume_range(muscle, months) == large_range
    for muscle in SMALL_MUSCLES:
        assert weekly_direct_volume_range(muscle, months) == small_range


@pytest.mark.parametrize(
    "muscle",
    [
        MuscleGroup.ABS,
        MuscleGroup.TRAPS,
        MuscleGroup.NECK,
        MuscleGroup.ADDUCTORS,
        MuscleGroup.ABDUCTORS,
        MuscleGroup.LEGS,
        MuscleGroup.OBLIQUES,
        MuscleGroup.LOWER_BACK,
    ],
)
def test_unclassified_muscles_keep_legacy_weekly_range_fallback(muscle: MuscleGroup) -> None:
    for months in (0, 6, 25, 60):
        assert weekly_direct_volume_range(muscle, months) is None


def test_session_direct_ranges_remain_unchanged_and_are_not_weekly_hard_caps() -> None:
    assert session_direct_volume_range(MuscleGroup.CHEST, 0) == (3, 6)
    assert session_direct_volume_range(MuscleGroup.CHEST, 6) == (4, 8)
    assert session_direct_volume_range(MuscleGroup.CHEST, 25) == (5, 10)
    assert session_direct_volume_range(MuscleGroup.BICEPS, 0) == (2, 4)
    assert session_direct_volume_range(MuscleGroup.BICEPS, 6) == (3, 6)
    assert session_direct_volume_range(MuscleGroup.BICEPS, 25) == (4, 8)


@pytest.mark.parametrize(
    ("months", "experience", "expected"),
    [
        (12, TrainingExperience.INTERMEDIATE, 24),
        (72, TrainingExperience.ADVANCED, 30),
    ],
)
def test_classified_planner_maximum_hard_uses_weekly_direct_range(
    months: int,
    experience: TrainingExperience,
    expected: int,
) -> None:
    _, plan = _plan(training_age_months=months, training_experience=experience)
    chest = next(target for target in plan.targets if target.muscle is MuscleGroup.CHEST)
    assert chest.maximum_hard == expected


def test_small_muscle_planner_maximum_hard_uses_weekly_direct_range() -> None:
    _, intermediate = _plan(
        training_age_months=12,
        training_experience=TrainingExperience.INTERMEDIATE,
    )
    _, advanced = _plan(
        training_age_months=72,
        training_experience=TrainingExperience.ADVANCED,
    )
    intermediate_biceps = next(
        target for target in intermediate.targets if target.muscle is MuscleGroup.BICEPS
    )
    advanced_biceps = next(
        target for target in advanced.targets if target.muscle is MuscleGroup.BICEPS
    )
    assert intermediate_biceps.maximum_hard == 20
    assert advanced_biceps.maximum_hard == 20
