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
    AthleteStateReplacementContext,
    AthleteStateSafetyContext,
    AthleteStateScheduleContext,
)
from app.exercises.enums import MuscleGroup
from app.workout_cycles.enums import (
    WorkoutCycleWeeklyCheckInDifficulty,
    WorkoutCycleWeeklyCheckInRecovery,
    WorkoutExerciseReplacementReason,
)
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
    recovery_values: tuple[WorkoutCycleWeeklyCheckInRecovery, ...] = (),
    difficulty_values: tuple[WorkoutCycleWeeklyCheckInDifficulty, ...] = (),
    lagging: tuple[MuscleGroup, ...] = (),
    progressing: tuple[MuscleGroup, ...] = (),
    disliked: tuple = (),
    uncomfortable: tuple = (),
    unavailable: tuple = (),
    pain_sensitive: tuple = (),
    replacement_context: tuple[AthleteStateReplacementContext, ...] = (),
    safety_context: tuple[AthleteStateSafetyContext, ...] = (),
) -> AthleteState:
    return AthleteState(
        user_id=uuid4(),
        adherence=AthleteStateAdherence(
            sessions_completed=19,
            planned_sessions=20,
            percent=adherence_percent,
        ),
        recovery_trend=AthleteStateRecoveryTrend(summary=recovery, values=recovery_values),
        difficulty_trend=AthleteStateDifficultyTrend(summary=difficulty, values=difficulty_values),
        persistent_disliked_exercises=disliked,
        uncomfortable_exercises=uncomfortable,
        unavailable_exercises=unavailable,
        pain_sensitive_exercises=pain_sensitive,
        replacement_context=replacement_context,
        safety_context=safety_context,
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
    assert decision.volume_context.previous_effective_sets_by_muscle == {MuscleGroup.CHEST: 10.0}
    assert decision.volume_context.confidence == 0.95
    assert decision.recovery_constraints.max_volume_increase_ratio == 0.1
    assert "PROGRESSION_SUPPORTED_BY_ADHERENCE_RECOVERY_DIFFICULTY" in decision.reason_codes
    assert "HIGH_ADHERENCE" in decision.reason_codes
    assert "GOOD_RECOVERY" in decision.reason_codes
    assert "PROGRESSION_ALLOWED" in decision.reason_codes


def test_poor_recovery_blocks_progression_and_reduces_demand() -> None:
    decision = decide_cycle_adaptation(
        _state(
            recovery=AthleteStateRecoverySummary.POOR,
            recovery_values=(
                WorkoutCycleWeeklyCheckInRecovery.POOR,
                WorkoutCycleWeeklyCheckInRecovery.POOR,
            ),
        ),
        _history(),
        RULESET,
    )

    assert decision.overall_action is CycleAdaptationAction.REDUCE
    assert decision.recovery_constraints.prevent_increase is True
    assert "POOR_RECOVERY_REQUIRES_REDUCTION" in decision.reason_codes


def test_single_poor_recovery_week_holds_progression() -> None:
    decision = decide_cycle_adaptation(
        _state(
            recovery=AthleteStateRecoverySummary.POOR,
            recovery_values=(WorkoutCycleWeeklyCheckInRecovery.POOR,),
        ),
        _history(),
        RULESET,
    )

    assert decision.overall_action is CycleAdaptationAction.MAINTAIN
    assert "POOR_RECOVERY" in decision.reason_codes
    assert "RECOVERY_LIMITED" in decision.reason_codes
    assert "PROGRESSION_HELD" in decision.reason_codes


def test_repeated_poor_recovery_weeks_reduce_demand() -> None:
    decision = decide_cycle_adaptation(
        _state(
            recovery=AthleteStateRecoverySummary.POOR,
            recovery_values=(
                WorkoutCycleWeeklyCheckInRecovery.POOR,
                WorkoutCycleWeeklyCheckInRecovery.POOR,
            ),
        ),
        _history(),
        RULESET,
    )

    assert decision.overall_action is CycleAdaptationAction.REDUCE
    assert "POOR_RECOVERY_REQUIRES_REDUCTION" in decision.reason_codes


def test_low_adherence_does_not_treat_prescribed_history_as_tolerated_volume() -> None:
    decision = decide_cycle_adaptation(
        _state(adherence_percent=50),
        _history(adherence=0.5, source="prescribed_plan"),
        RULESET,
    )

    assert decision.overall_action is CycleAdaptationAction.MAINTAIN
    assert decision.muscle_adjustments == ()
    assert decision.volume_context.previous_effective_sets_by_muscle == {MuscleGroup.CHEST: 5.0}
    assert "LOW_ADHERENCE_BLOCKS_PROGRESSION" in decision.reason_codes


def test_consistently_too_hard_feedback_reduces_demand() -> None:
    decision = decide_cycle_adaptation(
        _state(
            difficulty=AthleteStateDifficultySummary.TOO_HARD,
            difficulty_values=(
                WorkoutCycleWeeklyCheckInDifficulty.TOO_HARD,
                WorkoutCycleWeeklyCheckInDifficulty.TOO_HARD,
            ),
        ),
        _history(),
        RULESET,
    )

    assert decision.overall_action is CycleAdaptationAction.REDUCE
    assert "TOO_HARD_REQUIRES_REDUCTION" in decision.reason_codes
    assert "DIFFICULTY_TOO_HARD" in decision.reason_codes


def test_single_too_hard_week_holds_progression() -> None:
    decision = decide_cycle_adaptation(
        _state(
            difficulty=AthleteStateDifficultySummary.TOO_HARD,
            difficulty_values=(WorkoutCycleWeeklyCheckInDifficulty.TOO_HARD,),
        ),
        _history(),
        RULESET,
    )

    assert decision.overall_action is CycleAdaptationAction.MAINTAIN
    assert "DIFFICULTY_TOO_HARD" in decision.reason_codes
    assert "PROGRESSION_HELD" in decision.reason_codes


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


def test_pain_signal_is_a_hard_constraint_with_safety_reasons() -> None:
    exercise_id = uuid4()
    signal_ids = (uuid4(), uuid4())
    decision = decide_cycle_adaptation(
        _state(
            pain_sensitive=(exercise_id,),
            safety_context=(
                AthleteStateSafetyContext(
                    exercise_id=exercise_id,
                    signal_count=2,
                    source_safety_signal_ids=signal_ids,
                ),
            ),
        ),
        _history(),
        RULESET,
    )

    assert decision.overall_action is CycleAdaptationAction.REDUCE
    assert decision.recovery_constraints.prevent_increase is True
    assert decision.safety_constraints.blocked_exercises == (exercise_id,)
    assert decision.safety_constraints.signal_counts_by_exercise == {exercise_id: 2}
    assert "PAIN_SIGNAL_PRESENT" in decision.reason_codes
    assert "REPEATED_PAIN_SIGNAL" in decision.reason_codes
    assert "EXERCISE_BLOCKED_FOR_SAFETY" in decision.reason_codes
    assert "PROGRESSION_HELD_FOR_SAFETY" in decision.reason_codes
    assert set(signal_ids).issubset(decision.provenance.safety_signal_ids)


def test_pain_replacement_produces_only_an_eligible_safe_substitution() -> None:
    original_id = uuid4()
    alternative_id = uuid4()
    replacement_id = uuid4()
    safety_signal_id = uuid4()
    state = _state(
        pain_sensitive=(original_id,),
        replacement_context=(
            AthleteStateReplacementContext(
                original_exercise_id=original_id,
                replacement_exercise_id=alternative_id,
                persistent_count=0,
                this_time_count=1,
                reasons=(WorkoutExerciseReplacementReason.PAIN_OR_DISCOMFORT,),
                source_replacement_ids=(replacement_id,),
                safe=True,
            ),
        ),
        safety_context=(
            AthleteStateSafetyContext(
                exercise_id=original_id,
                signal_count=1,
                source_safety_signal_ids=(safety_signal_id,),
                source_replacement_ids=(replacement_id,),
            ),
        ),
    )

    decision = decide_cycle_adaptation(state, _history(), RULESET)

    assert len(decision.safety_constraints.safe_substitutions) == 1
    substitution = decision.safety_constraints.safe_substitutions[0]
    assert substitution.blocked_exercise_id == original_id
    assert substitution.replacement_exercise_id == alternative_id
    assert substitution.source_replacement_ids == (replacement_id,)
    assert substitution.source_safety_signal_ids == (safety_signal_id,)
    assert "SAFE_SUBSTITUTION_REQUIRED" in decision.reason_codes


def test_unsafe_or_blocked_pain_replacements_are_not_safe_substitutions() -> None:
    original_id = uuid4()
    alternative_id = uuid4()
    context = AthleteStateReplacementContext(
        original_exercise_id=original_id,
        replacement_exercise_id=alternative_id,
        persistent_count=0,
        this_time_count=1,
        reasons=(WorkoutExerciseReplacementReason.PAIN_OR_DISCOMFORT,),
        source_replacement_ids=(uuid4(),),
        safe=False,
    )
    decision = decide_cycle_adaptation(
        _state(
            pain_sensitive=(original_id, alternative_id),
            replacement_context=(context,),
        ),
        _history(),
        RULESET,
    )

    assert decision.safety_constraints.safe_substitutions == ()
    assert decision.safety_constraints.blocked_exercises == tuple(
        sorted((original_id, alternative_id), key=str)
    )


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
    assert "PROGRESSION_HELD" in missing.reason_codes
    assert missing.safety_constraints.blocked_exercises == ()
    assert "PAIN_SIGNAL_PRESENT" not in missing.reason_codes
    assert conflicting.overall_action is CycleAdaptationAction.INCREASE


def test_good_recovery_with_low_adherence_holds_progression() -> None:
    decision = decide_cycle_adaptation(
        _state(adherence_percent=50),
        _history(adherence=0.5),
        RULESET,
    )

    assert decision.overall_action is CycleAdaptationAction.MAINTAIN
    assert "GOOD_RECOVERY" in decision.reason_codes
    assert "LOW_ADHERENCE" in decision.reason_codes
    assert "PROGRESSION_HELD" in decision.reason_codes


def test_high_adherence_with_poor_recovery_holds_or_reduces_conservatively() -> None:
    decision = decide_cycle_adaptation(
        _state(
            recovery=AthleteStateRecoverySummary.POOR,
            recovery_values=(WorkoutCycleWeeklyCheckInRecovery.POOR,),
        ),
        _history(),
        RULESET,
    )

    assert decision.overall_action is CycleAdaptationAction.MAINTAIN
    assert "HIGH_ADHERENCE" in decision.reason_codes
    assert "POOR_RECOVERY" in decision.reason_codes
    assert "RECOVERY_LIMITED" in decision.reason_codes


def test_single_poor_recovery_takes_precedence_over_easy_difficulty() -> None:
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

    assert decision.overall_action is CycleAdaptationAction.MAINTAIN
    assert "POOR_RECOVERY" in decision.reason_codes
    assert "PROGRESSION_HELD" in decision.reason_codes
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


def test_persistent_dislike_is_deprioritized_but_not_blocked() -> None:
    exercise_id = uuid4()
    decision = decide_cycle_adaptation(
        _state(disliked=(exercise_id,)),
        _history(),
        RULESET,
    )

    assert decision.preference_constraints.disliked_exercises == (exercise_id,)
    assert decision.safety_constraints.blocked_exercises == ()
    assert "PERSISTENT_EXERCISE_DISLIKE" in decision.reason_codes


def test_persistent_uncomfortable_is_a_preference_not_a_safety_block() -> None:
    exercise_id = uuid4()
    decision = decide_cycle_adaptation(
        _state(uncomfortable=(exercise_id,)),
        _history(),
        RULESET,
    )

    assert decision.preference_constraints.disliked_exercises == (exercise_id,)
    assert decision.safety_constraints.blocked_exercises == ()
    assert "PERSISTENT_EXERCISE_DISCOMFORT" in decision.reason_codes


def test_persistent_equipment_unavailable_is_an_availability_constraint() -> None:
    exercise_id = uuid4()
    decision = decide_cycle_adaptation(
        _state(unavailable=(exercise_id,)),
        _history(),
        RULESET,
    )

    assert decision.preference_constraints.unavailable_exercises == (exercise_id,)
    assert decision.safety_constraints.blocked_exercises == ()
    assert "EQUIPMENT_UNAVAILABLE" in decision.reason_codes


def test_availability_constraint_overrides_a_persistent_dislike() -> None:
    exercise_id = uuid4()
    decision = decide_cycle_adaptation(
        _state(disliked=(exercise_id,), unavailable=(exercise_id,)),
        _history(),
        RULESET,
    )

    assert decision.preference_constraints.disliked_exercises == ()
    assert decision.preference_constraints.unavailable_exercises == (exercise_id,)


def test_repeated_persistent_replacements_prefer_the_confirmed_alternative() -> None:
    original_id = uuid4()
    alternative_id = uuid4()
    replacement_ids = (uuid4(), uuid4())
    context = AthleteStateReplacementContext(
        original_exercise_id=original_id,
        replacement_exercise_id=alternative_id,
        persistent_count=2,
        this_time_count=0,
        reasons=(WorkoutExerciseReplacementReason.DISLIKE,),
        source_replacement_ids=replacement_ids,
    )

    decision = decide_cycle_adaptation(
        _state(replacement_context=(context,)),
        _history(),
        RULESET,
    )

    preferred = decision.preference_constraints.preferred_alternatives
    assert len(preferred) == 1
    assert preferred[0].original_exercise_id == original_id
    assert preferred[0].replacement_exercise_id == alternative_id
    assert preferred[0].strength == 2
    assert set(preferred[0].source_replacement_ids) == set(replacement_ids)
    assert "REPEATED_REPLACEMENT" in decision.reason_codes
    assert "PREFERRED_ALTERNATIVE" in decision.reason_codes
    assert set(decision.provenance.replacement_ids) == set(replacement_ids)


def test_this_time_replacements_have_no_future_preference_effect() -> None:
    context = AthleteStateReplacementContext(
        original_exercise_id=uuid4(),
        replacement_exercise_id=uuid4(),
        persistent_count=0,
        this_time_count=3,
        reasons=(WorkoutExerciseReplacementReason.DISLIKE,),
        source_replacement_ids=(uuid4(), uuid4(), uuid4()),
    )

    decision = decide_cycle_adaptation(
        _state(replacement_context=(context,)),
        _history(),
        RULESET,
    )

    assert decision.preference_constraints.preferred_alternatives == ()
    assert decision.provenance.replacement_ids == tuple(
        sorted(context.source_replacement_ids, key=str)
    )


def test_more_repeated_persistent_replacements_have_stronger_preference() -> None:
    first = AthleteStateReplacementContext(
        original_exercise_id=uuid4(),
        replacement_exercise_id=uuid4(),
        persistent_count=2,
        reasons=(WorkoutExerciseReplacementReason.UNCOMFORTABLE,),
        source_replacement_ids=(uuid4(), uuid4()),
    )
    second = AthleteStateReplacementContext(
        original_exercise_id=uuid4(),
        replacement_exercise_id=uuid4(),
        persistent_count=3,
        reasons=(WorkoutExerciseReplacementReason.DISLIKE,),
        source_replacement_ids=(uuid4(), uuid4(), uuid4()),
    )

    decision = decide_cycle_adaptation(
        _state(replacement_context=(first, second)),
        _history(),
        RULESET,
    )

    preferred = decision.preference_constraints.preferred_alternatives
    assert [item.strength for item in preferred] == [3, 2]


def test_safety_overrides_a_preferred_alternative() -> None:
    alternative_id = uuid4()
    context = AthleteStateReplacementContext(
        original_exercise_id=uuid4(),
        replacement_exercise_id=alternative_id,
        persistent_count=2,
        reasons=(WorkoutExerciseReplacementReason.DISLIKE,),
        source_replacement_ids=(uuid4(), uuid4()),
    )

    decision = decide_cycle_adaptation(
        _state(pain_sensitive=(alternative_id,), replacement_context=(context,)),
        _history(),
        RULESET,
    )

    assert decision.preference_constraints.preferred_alternatives == ()
    assert decision.safety_constraints.blocked_exercises == (alternative_id,)
    assert "PREFERENCE_OVERRIDDEN_BY_SAFETY" in decision.reason_codes


def test_replacement_preference_output_is_deterministic_for_conflicting_input_order() -> None:
    first = AthleteStateReplacementContext(
        original_exercise_id=uuid4(),
        replacement_exercise_id=uuid4(),
        persistent_count=2,
        reasons=(WorkoutExerciseReplacementReason.DISLIKE,),
        source_replacement_ids=(uuid4(), uuid4()),
    )
    second = AthleteStateReplacementContext(
        original_exercise_id=uuid4(),
        replacement_exercise_id=uuid4(),
        persistent_count=2,
        reasons=(WorkoutExerciseReplacementReason.EQUIPMENT_UNAVAILABLE,),
        source_replacement_ids=(uuid4(), uuid4()),
    )
    state = _state(replacement_context=(first, second))

    forward = decide_cycle_adaptation(state, _history(), RULESET)
    reverse = decide_cycle_adaptation(
        state.model_copy(update={"replacement_context": (second, first)}),
        _history(),
        RULESET,
    )

    assert forward.to_snapshot_json() == reverse.to_snapshot_json()
