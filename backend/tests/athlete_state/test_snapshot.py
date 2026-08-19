from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

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


def test_first_time_athlete_has_neutral_snapshot_and_stable_serialization(
    db: Session,
) -> None:
    user = _user(db)
    builder = AthleteStateBuilder(db)

    state = builder.build(user.id)
    snapshot = state.to_snapshot()
    snapshot_json = state.to_snapshot_json()

    assert state.current_cycle_id is None
    assert state.adherence.percent is None
    assert state.recovery_trend.summary == "unknown"
    assert state.difficulty_trend.summary == "unknown"
    assert snapshot["user_id"] == str(user.id)
    assert snapshot == state.to_snapshot()
    assert snapshot["recovery_trend"]["reason_codes"] == ["no_recovery_data"]
    assert snapshot["provenance"]["cycle_ids"] == []
    assert "comparison_result" not in snapshot_json
    assert snapshot_json == state.to_snapshot_json()


def test_partial_weekly_feedback_keeps_unknown_direction_without_fabrication(
    db: Session,
) -> None:
    user = _user(db)
    _plan, _prescribed, cycle, *_ = _plan_with_cycle(db, user.id)
    assert cycle is not None
    db.add(
        WorkoutCycleWeeklyCheckIn(
            user_id=user.id,
            cycle_id=cycle.id,
            week_number=1,
            sessions_completed=1,
            perceived_difficulty=WorkoutCycleWeeklyCheckInDifficulty.APPROPRIATE,
            recovery_rating=WorkoutCycleWeeklyCheckInRecovery.GOOD,
            has_pain_or_limitation=False,
        )
    )
    db.commit()

    state = AthleteStateBuilder(db).build(user.id)

    assert state.adherence.percent == 100.0
    assert state.recovery_trend.summary == "good"
    assert state.difficulty_trend.summary == "appropriate"
    assert state.recovery_trend.direction.value == "unknown"
    assert state.difficulty_trend.direction.value == "unknown"


def test_feedback_survives_when_body_analysis_is_missing(db: Session) -> None:
    user, cycle = _cycle_with_snapshots(db, include_start=False, include_end=False)
    feedback = CompletionFeedbackInput(
        strength_progress=WorkoutCycleFeedbackProgress.IMPROVED,
        progressed_muscles=[MuscleGroup.CHEST],
        lagging_muscles=[MuscleGroup.BACK],
    )
    complete_cycle(db, cycle_id=cycle.id, user_id=user.id, feedback=feedback)

    state = AthleteStateBuilder(db).build(user.id)

    assert state.progressing_muscles == (MuscleGroup.CHEST,)
    assert state.lagging_muscles == (MuscleGroup.BACK,)
    assert state.body_progress.improved_areas == ()
    assert state.body_progress.lagging_areas == ()
    assert state.body_progress.comparison_ids
    assert state.provenance.body_analysis_ids == ()


def test_subjective_and_body_progress_evidence_remain_separate(db: Session) -> None:
    user, cycle = _cycle_with_snapshots(db)
    feedback = CompletionFeedbackInput(
        strength_progress=WorkoutCycleFeedbackProgress.IMPROVED,
        progressed_muscles=[MuscleGroup.CHEST],
        lagging_muscles=[MuscleGroup.BACK],
    )
    complete_cycle(db, cycle_id=cycle.id, user_id=user.id, feedback=feedback)

    state = AthleteStateBuilder(db).build(user.id)

    assert state.progressing_muscles == (MuscleGroup.CHEST,)
    assert state.lagging_muscles == (MuscleGroup.BACK,)
    assert state.body_progress.improved_areas == (BodyArea.SHOULDERS,)
    assert state.provenance.end_feedback_ids
    assert state.provenance.body_progress_comparison_ids


def test_repeated_persistent_replacements_are_deduplicated_but_traceable(
    db: Session,
) -> None:
    user, cycle = _cycle_with_snapshots(db)
    prescribed_id, original_id, safe_id = _prescribed_and_safe_ids(cycle)
    for _ in range(2):
        record_exercise_replacement(
            db,
            user_id=user.id,
            workout_plan_exercise_id=prescribed_id,
            replacement_exercise_id=safe_id,
            reason=WorkoutExerciseReplacementReason.DISLIKE,
            scope=WorkoutExerciseReplacementScope.PERSISTENT,
        )

    state = AthleteStateBuilder(db).build(user.id)

    assert state.persistent_disliked_exercises == (original_id,)
    assert len(state.provenance.replacement_ids) == 2
    assert len(state.provenance.preference_ids) == 1
    assert len(state.provenance.preference_source_replacement_ids) == 1
    assert len(state.replacement_context) == 1
    assert state.replacement_context[0].persistent_count == 2
    assert state.replacement_context[0].this_time_count == 0
    assert state.replacement_context[0].source_replacement_ids == state.provenance.replacement_ids


def test_newer_weekly_evidence_overrides_older_evidence_in_recent_summary(
    db: Session,
) -> None:
    user = _user(db)
    _plan, _prescribed, cycle, *_ = _plan_with_cycle(db, user.id)
    assert cycle is not None
    cycle.duration_weeks = 6
    recoveries = (
        WorkoutCycleWeeklyCheckInRecovery.POOR,
        WorkoutCycleWeeklyCheckInRecovery.GOOD,
        WorkoutCycleWeeklyCheckInRecovery.GOOD,
        WorkoutCycleWeeklyCheckInRecovery.GOOD,
        WorkoutCycleWeeklyCheckInRecovery.GOOD,
    )
    db.add_all(
        [
            WorkoutCycleWeeklyCheckIn(
                user_id=user.id,
                cycle_id=cycle.id,
                week_number=week,
                sessions_completed=1,
                perceived_difficulty=WorkoutCycleWeeklyCheckInDifficulty.APPROPRIATE,
                recovery_rating=recovery,
                has_pain_or_limitation=False,
            )
            for week, recovery in enumerate(recoveries, start=1)
        ]
    )
    db.commit()

    state = AthleteStateBuilder(db).build(user.id)

    assert state.recovery_trend.values[0] is WorkoutCycleWeeklyCheckInRecovery.POOR
    assert state.recovery_trend.summary == "good"
    assert state.recovery_trend.reason_codes == ("all_recent_recovery_good",)


def test_other_users_never_appear_in_snapshot(db: Session) -> None:
    owner, _owner_cycle = _cycle_with_snapshots(db)
    other, other_cycle = _cycle_with_snapshots(db)
    prescribed_id, _original_id, safe_id = _prescribed_and_safe_ids(other_cycle)
    record_exercise_replacement(
        db,
        user_id=other.id,
        workout_plan_exercise_id=prescribed_id,
        replacement_exercise_id=safe_id,
        reason=WorkoutExerciseReplacementReason.DISLIKE,
        scope=WorkoutExerciseReplacementScope.PERSISTENT,
    )

    snapshot = AthleteStateBuilder(db).build(owner.id).to_snapshot()

    assert snapshot["user_id"] == str(owner.id)
    assert str(other.id) not in str(snapshot)
