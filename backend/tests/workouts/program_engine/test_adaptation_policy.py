from uuid import uuid4

from app.athlete_state.schemas import (
    AthleteState,
    AthleteStateAdherence,
    AthleteStateBodyProgress,
    AthleteStateDifficultySummary,
    AthleteStateDifficultyTrend,
    AthleteStateProvenance,
    AthleteStateRecoverySummary,
    AthleteStateRecoveryTrend,
    AthleteStateScheduleContext,
)
from app.exercises.enums import MuscleGroup
from app.workouts.program_engine.adaptation_policy import (
    CycleAdaptationAction,
    decide_cycle_adaptation,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET
from app.workouts.program_engine.schemas import RecentTrainingHistory


def _state(
    *,
    adherence_percent: float | None = 95,
    recovery: AthleteStateRecoverySummary = AthleteStateRecoverySummary.GOOD,
    difficulty: AthleteStateDifficultySummary = AthleteStateDifficultySummary.APPROPRIATE,
    lagging: tuple[MuscleGroup, ...] = (),
    progressing: tuple[MuscleGroup, ...] = (),
    disliked: tuple = (),
    unavailable: tuple = (),
    pain_sensitive: tuple = (),
) -> AthleteState:
    return AthleteState(
        user_id=uuid4(),
        adherence=AthleteStateAdherence(
            sessions_completed=19,
            planned_sessions=20,
            percent=adherence_percent,
        ),
        recovery_trend=AthleteStateRecoveryTrend(summary=recovery),
        difficulty_trend=AthleteStateDifficultyTrend(summary=difficulty),
        persistent_disliked_exercises=disliked,
        unavailable_exercises=unavailable,
        pain_sensitive_exercises=pain_sensitive,
        priority_muscles=lagging,
        progressing_muscles=progressing,
        lagging_muscles=lagging,
        schedule=AthleteStateScheduleContext(),
        body_progress=AthleteStateBodyProgress(),
        provenance=AthleteStateProvenance(
            cycle_ids=(uuid4(),),
            weekly_check_in_ids=(uuid4(),),
            end_feedback_ids=(uuid4(),),
            preference_ids=(uuid4(),),
            safety_signal_ids=(uuid4(),) if pain_sensitive else (),
            workout_plan_ids=(uuid4(),),
        ),
    )


def _history(
    *, adherence: float = 0.95, source: str = "observed_effective"
) -> RecentTrainingHistory:
    return RecentTrainingHistory(
        completed_session_ratio=adherence,
        previous_weekly_effective_sets_by_muscle={MuscleGroup.CHEST: 10.0},
        previous_volume_source=source,
        previous_volume_confidence=adherence,
    )


def test_good_supported_history_allows_conservative_increase() -> None:
    decision = decide_cycle_adaptation(_state(), _history(), RULESET)

    assert decision.overall_action is CycleAdaptationAction.INCREASE
    assert decision.volume_context.previous_effective_sets_by_muscle == {
        MuscleGroup.CHEST: 10.0
    }
    assert decision.volume_context.confidence == 0.95
    assert decision.recovery_constraints.max_volume_increase_ratio == 0.1
    assert "PROGRESSION_SUPPORTED_BY_ADHERENCE_RECOVERY_DIFFICULTY" in decision.reason_codes


def test_poor_recovery_blocks_progression_and_reduces_demand() -> None:
    decision = decide_cycle_adaptation(
        _state(recovery=AthleteStateRecoverySummary.POOR),
        _history(),
        RULESET,
    )

    assert decision.overall_action is CycleAdaptationAction.REDUCE
    assert decision.recovery_constraints.prevent_increase is True
    assert "POOR_RECOVERY_REQUIRES_REDUCTION" in decision.reason_codes


def test_low_adherence_does_not_treat_prescribed_history_as_tolerated_volume() -> None:
    decision = decide_cycle_adaptation(
        _state(adherence_percent=50),
        _history(adherence=0.5, source="prescribed_plan"),
        RULESET,
    )

    assert decision.overall_action is CycleAdaptationAction.MAINTAIN
    assert decision.muscle_adjustments == ()
    assert decision.volume_context.previous_effective_sets_by_muscle == {
        MuscleGroup.CHEST: 5.0
    }
    assert "LOW_ADHERENCE_BLOCKS_PROGRESSION" in decision.reason_codes


def test_consistently_too_hard_feedback_reduces_demand() -> None:
    decision = decide_cycle_adaptation(
        _state(difficulty=AthleteStateDifficultySummary.TOO_HARD),
        _history(),
        RULESET,
    )

    assert decision.overall_action is CycleAdaptationAction.REDUCE
    assert "TOO_HARD_REQUIRES_REDUCTION" in decision.reason_codes


def test_lagging_muscle_gets_one_conservative_adjustment_when_supported() -> None:
    decision = decide_cycle_adaptation(
        _state(lagging=(MuscleGroup.QUADRICEPS,), progressing=(MuscleGroup.CHEST,)),
        _history(),
        RULESET,
    )

    assert len(decision.muscle_adjustments) == 1
    adjustment = decision.muscle_adjustments[0]
    assert adjustment.muscle is MuscleGroup.QUADRICEPS
    assert adjustment.volume_delta_sets == 1
    assert adjustment.priority_delta == 1
    assert "PROGRESSING_MUSCLE_NOT_AUTOMATICALLY_INCREASED" in decision.reason_codes


def test_pain_safety_overrides_progression_and_preference() -> None:
    exercise_id = uuid4()
    decision = decide_cycle_adaptation(
        _state(disliked=(exercise_id,), pain_sensitive=(exercise_id,)),
        _history(),
        RULESET,
    )

    assert decision.overall_action is CycleAdaptationAction.REDUCE
    assert decision.safety_constraints.blocked_exercises == (exercise_id,)
    assert decision.preference_constraints.disliked_exercises == ()
    assert "SAFETY_OVERRIDES_PREFERENCE" in decision.reason_codes


def test_missing_or_conflicting_data_falls_back_conservatively() -> None:
    missing = decide_cycle_adaptation(
        _state(
            adherence_percent=None,
            recovery=AthleteStateRecoverySummary.UNKNOWN,
            difficulty=AthleteStateDifficultySummary.UNKNOWN,
        ),
        RecentTrainingHistory(),
        RULESET,
    )
    conflicting = decide_cycle_adaptation(
        _state(difficulty=AthleteStateDifficultySummary.TOO_EASY),
        _history(),
        RULESET,
    )

    assert missing.overall_action is CycleAdaptationAction.MAINTAIN
    assert "INSUFFICIENT_RELIABLE_EVIDENCE" in missing.reason_codes
    assert conflicting.overall_action is CycleAdaptationAction.INCREASE


def test_recovery_conflict_takes_precedence_over_easy_difficulty() -> None:
    state = _state(
        recovery=AthleteStateRecoverySummary.POOR,
        difficulty=AthleteStateDifficultySummary.TOO_EASY,
    )
    decision = decide_cycle_adaptation(
        state,
        _history(),
        RULESET,
    )
    repeated = decide_cycle_adaptation(state, _history(), RULESET)

    assert decision.overall_action is CycleAdaptationAction.REDUCE
    assert decision.reason_codes[0] == "POOR_RECOVERY_REQUIRES_REDUCTION"
    assert decision.to_snapshot_json() == repeated.to_snapshot_json()


def test_preferences_and_provenance_are_preserved_in_decision() -> None:
    disliked_id = uuid4()
    unavailable_id = uuid4()
    state = _state(disliked=(disliked_id,), unavailable=(unavailable_id,))

    decision = decide_cycle_adaptation(state, _history(), RULESET)

    assert decision.preference_constraints.disliked_exercises == (disliked_id,)
    assert decision.preference_constraints.unavailable_exercises == (unavailable_id,)
    assert decision.provenance.cycle_ids == state.provenance.cycle_ids
    assert decision.to_snapshot()["overall_action"] == "increase"
