from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.schemas import RecentTrainingHistory
from app.workouts.program_engine.volume_history import derive_previous_volume_baseline


def test_first_cycle_has_no_history_baseline() -> None:
    baseline = derive_previous_volume_baseline(RecentTrainingHistory())

    assert baseline.direct_sets_by_muscle == {}
    assert baseline.effective_sets_by_muscle == {}
    assert baseline.confidence == 0


def test_high_adherence_preserves_previous_direct_and_effective_volume() -> None:
    history = RecentTrainingHistory(
        completed_session_ratio=1.0,
        previous_weekly_direct_sets_by_muscle={MuscleGroup.CHEST: 8.0},
        previous_weekly_effective_sets_by_muscle={MuscleGroup.CHEST: 10.0},
        previous_volume_source="prescribed_plan",
    )

    baseline = derive_previous_volume_baseline(history)

    assert baseline.direct_sets_by_muscle == {MuscleGroup.CHEST: 8.0}
    assert baseline.effective_sets_by_muscle == {MuscleGroup.CHEST: 10.0}
    assert baseline.confidence == 1.0


def test_low_adherence_scales_prescribed_volume_instead_of_claiming_full_completion() -> None:
    history = RecentTrainingHistory(
        completed_session_ratio=0.25,
        previous_weekly_direct_sets_by_muscle={MuscleGroup.CHEST: 8.0},
        previous_weekly_effective_sets_by_muscle={MuscleGroup.CHEST: 10.0},
        previous_volume_source="prescribed_plan",
    )

    baseline = derive_previous_volume_baseline(history)

    assert baseline.direct_sets_by_muscle == {MuscleGroup.CHEST: 2.0}
    assert baseline.effective_sets_by_muscle == {MuscleGroup.CHEST: 2.5}
    assert baseline.confidence == 0.25


def test_legacy_direct_plan_metrics_are_also_scaled_when_source_is_prescribed() -> None:
    history = RecentTrainingHistory(
        completed_session_ratio=0.25,
        previous_weekly_direct_sets_by_muscle={MuscleGroup.CHEST: 8.0},
        previous_volume_source="prescribed_plan",
    )

    baseline = derive_previous_volume_baseline(history)

    assert baseline.direct_sets_by_muscle == {MuscleGroup.CHEST: 2.0}
    assert baseline.effective_sets_by_muscle == {}


def test_muscle_specific_history_and_reason_codes_are_deterministic() -> None:
    history = RecentTrainingHistory(
        completed_session_ratio=0.8,
        previous_weekly_direct_sets_by_muscle={
            MuscleGroup.CHEST: 8.0,
            MuscleGroup.TRICEPS: 4.0,
        },
        previous_weekly_effective_sets_by_muscle={
            MuscleGroup.CHEST: 10.0,
            MuscleGroup.TRICEPS: 6.0,
        },
        previous_volume_source="prescribed_plan",
        previous_volume_reason_codes=("HISTORY_FROM_COMPLETED_PLAN",),
    )

    first = derive_previous_volume_baseline(history)
    second = derive_previous_volume_baseline(history)

    assert first == second
    assert first.effective_sets_by_muscle[MuscleGroup.TRICEPS] == 4.8
    assert "HISTORY_SCALED_BY_ADHERENCE" in first.reason_codes
