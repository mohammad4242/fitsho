from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.athlete_state.schemas import AthleteStateTrendDirection
from app.athlete_state.service import AthleteStateBuilder
from app.body_analysis.enums import BodyArea
from app.exercises.enums import MuscleGroup
from app.workout_cycles.enums import (
    WorkoutCycleFeedbackProgress,
    WorkoutCycleWeeklyCheckInDifficulty,
    WorkoutCycleWeeklyCheckInRecovery,
    WorkoutExerciseReplacementReason,
    WorkoutExerciseReplacementScope,
)
from app.workout_cycles.models import WorkoutCycleWeeklyCheckIn
from app.workout_cycles.schemas import CompletionFeedbackInput
from app.workout_cycles.service import complete_cycle, record_exercise_replacement
from tests.workout_cycles.test_cycle_body_progress_comparison import _cycle_with_snapshots
from tests.workout_cycles.test_replacement_api import _plan_with_cycle, _user


def _prescribed_and_safe_ids(cycle) -> tuple[UUID, UUID, UUID]:
    prescribed = cycle.workout_plan.days[0].exercises[0]
    return prescribed.id, prescribed.exercise_id, UUID(prescribed.substitution_exercise_ids[0])


def test_athlete_state_aggregates_cycle_history_and_preserves_provenance(
    db: Session,
) -> None:
    user, cycle = _cycle_with_snapshots(db)
    prescribed_id, original_id, safe_id = _prescribed_and_safe_ids(cycle)
    first_check_in = WorkoutCycleWeeklyCheckIn(
        user_id=user.id,
        cycle_id=cycle.id,
        week_number=1,
        sessions_completed=0,
        perceived_difficulty=WorkoutCycleWeeklyCheckInDifficulty.HARD,
        recovery_rating=WorkoutCycleWeeklyCheckInRecovery.POOR,
        has_pain_or_limitation=False,
    )
    second_check_in = WorkoutCycleWeeklyCheckIn(
        user_id=user.id,
        cycle_id=cycle.id,
        week_number=2,
        sessions_completed=1,
        perceived_difficulty=WorkoutCycleWeeklyCheckInDifficulty.APPROPRIATE,
        recovery_rating=WorkoutCycleWeeklyCheckInRecovery.GOOD,
        has_pain_or_limitation=False,
    )
    db.add_all([first_check_in, second_check_in])
    db.commit()
    record_exercise_replacement(
        db,
        user_id=user.id,
        workout_plan_exercise_id=prescribed_id,
        replacement_exercise_id=safe_id,
        reason=WorkoutExerciseReplacementReason.DISLIKE,
        scope=WorkoutExerciseReplacementScope.PERSISTENT,
    )
    record_exercise_replacement(
        db,
        user_id=user.id,
        workout_plan_exercise_id=prescribed_id,
        replacement_exercise_id=safe_id,
        reason=WorkoutExerciseReplacementReason.PAIN_OR_DISCOMFORT,
        scope=WorkoutExerciseReplacementScope.THIS_TIME,
    )
    feedback = CompletionFeedbackInput(
        strength_progress=WorkoutCycleFeedbackProgress.IMPROVED,
        progressed_muscles=[MuscleGroup.CHEST],
        lagging_muscles=[MuscleGroup.BACK],
        next_training_days=4,
        next_session_duration_minutes=60,
    )
    complete_cycle(db, cycle_id=cycle.id, user_id=user.id, feedback=feedback)

    state = AthleteStateBuilder(db).build(user.id)

    assert state.user_id == user.id
    assert state.adherence.sessions_completed == 1
    assert state.adherence.planned_sessions == 2
    assert state.adherence.percent == 50.0
    assert state.recovery_trend.latest is WorkoutCycleWeeklyCheckInRecovery.GOOD
    assert state.recovery_trend.direction is AthleteStateTrendDirection.INCREASING
    assert state.difficulty_trend.latest is WorkoutCycleWeeklyCheckInDifficulty.APPROPRIATE
    assert state.difficulty_trend.direction is AthleteStateTrendDirection.DECREASING
    assert original_id in state.persistent_disliked_exercises
    assert original_id in state.pain_sensitive_exercises
    assert original_id not in state.unavailable_exercises
    assert MuscleGroup.CHEST in state.progressing_muscles
    assert MuscleGroup.BACK in state.lagging_muscles
    assert MuscleGroup.BACK in state.priority_muscles
    assert BodyArea.SHOULDERS in state.body_progress.improved_areas
    assert state.provenance.cycle_ids == (cycle.id,)
    assert first_check_in.id in state.provenance.weekly_check_in_ids
    assert second_check_in.id in state.provenance.weekly_check_in_ids
    assert state.provenance.end_feedback_ids
    assert state.provenance.preference_source_replacement_ids
    assert state.provenance.safety_signal_ids
    assert state.provenance.body_progress_comparison_ids


def test_athlete_state_missing_optional_data_is_safe(db: Session) -> None:
    user = _user(db)
    _plan, _prescribed, cycle, _original, _safe, _unsafe = _plan_with_cycle(db, user.id)
    assert cycle is not None

    state = AthleteStateBuilder(db).build(user.id)

    assert state.current_cycle_id == cycle.id
    assert state.adherence.percent is None
    assert state.recovery_trend.latest is None
    assert state.difficulty_trend.latest is None
    assert state.persistent_disliked_exercises == ()
    assert state.pain_sensitive_exercises == ()
    assert state.body_progress.comparison_ids == ()
    assert state.provenance.weekly_check_in_ids == ()


def test_athlete_state_never_includes_another_users_data(db: Session) -> None:
    owner, owner_cycle = _cycle_with_snapshots(db)
    other, other_cycle = _cycle_with_snapshots(db)
    _prescribed_id, other_original_id, other_safe_id = _prescribed_and_safe_ids(other_cycle)
    record_exercise_replacement(
        db,
        user_id=other.id,
        workout_plan_exercise_id=_prescribed_id,
        replacement_exercise_id=other_safe_id,
        reason=WorkoutExerciseReplacementReason.DISLIKE,
        scope=WorkoutExerciseReplacementScope.PERSISTENT,
    )
    complete_cycle(db, cycle_id=owner_cycle.id, user_id=owner.id)

    state = AthleteStateBuilder(db).build(owner.id)

    assert other_original_id not in state.persistent_disliked_exercises
    assert all(cycle_id != other_cycle.id for cycle_id in state.provenance.cycle_ids)
