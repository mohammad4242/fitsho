from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    ExerciseType,
    MediaType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.exercises.models import Exercise
from app.workout_cycles.enums import WorkoutCycleExerciseFeedbackType, WorkoutCycleStatus
from app.workout_cycles.models import WorkoutCycle, WorkoutCycleExerciseFeedback
from app.workout_cycles.schemas import WorkoutCycleExerciseFeedbackInput
from app.workout_cycles.service import (
    WorkoutCycleExerciseFeedbackDuplicateError,
    WorkoutCycleExerciseFeedbackPlanExerciseNotFoundError,
    record_workout_cycle_exercise_feedback,
)
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanExercise


def _user(db: Session, prefix: str = "exercise-feedback") -> User:
    user = User(email=f"{prefix}-{uuid4()}@example.com", password_hash="hash")
    db.add(user)
    db.flush()
    return user


def _exercise(db: Session, slug: str) -> Exercise:
    exercise = Exercise(
        slug=f"{slug}-{uuid4().hex}",
        name_en=slug.replace("-", " ").title(),
        name_fa=f"حرکت {slug}",
        body_region=BodyRegion.UPPER_BODY,
        primary_muscle=MuscleGroup.CHEST,
        muscle_focus=MuscleFocus.MID_CHEST,
        difficulty=Difficulty.BEGINNER,
        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        exercise_type=ExerciseType.COMPOUND,
        instructions_en=["Set up.", "Move safely.", "Finish."],
        instructions_fa=["آماده شو.", "ایمن حرکت کن.", "تمام کن."],
        safety_notes_en=["Move with control."],
        safety_notes_fa=["کنترل‌شده حرکت کن."],
        media_path="/exercises/exercise-placeholder.svg",
        media_type=MediaType.PLACEHOLDER,
        is_active=True,
        is_programmable=True,
        needs_review=False,
    )
    db.add(exercise)
    db.flush()
    return exercise


def _cycle_with_prescription(
    db: Session,
    *,
    user: User | None = None,
    plan_status: WorkoutPlanStatus = WorkoutPlanStatus.ACTIVE,
) -> tuple[User, WorkoutCycle, WorkoutPlanExercise, Exercise]:
    owner = user or _user(db)
    exercise = _exercise(db, "prescribed")
    plan = WorkoutPlan(
        user_id=owner.id,
        status=plan_status,
        generation_signature="a" * 64,
        profile_snapshot={"plan_duration_weeks": 4},
        provider="fake",
        model_id="fake-model",
        prompt_version="v1",
        generation_policy_version="v1",
        candidate_set_hash="b" * 64,
        generation_method="coach_review",
    )
    day = WorkoutDay(
        day_number=1,
        title_en="Upper body",
        title_fa="بالاتنه",
        estimated_duration_minutes=30,
    )
    prescribed = WorkoutPlanExercise(
        exercise_id=exercise.id,
        order_index=1,
        sets=3,
        reps_min=8,
        reps_max=12,
        rest_seconds=90,
        rir=2,
        estimated_minutes=5,
        exercise_snapshot={},
    )
    day.exercises.append(prescribed)
    plan.days.append(day)
    db.add(plan)
    db.flush()
    cycle = WorkoutCycle(
        user_id=owner.id,
        workout_plan_id=plan.id,
        duration_weeks=4,
        status=WorkoutCycleStatus.ACTIVE,
    )
    db.add(cycle)
    db.flush()
    return owner, cycle, prescribed, exercise


def test_valid_feedback_persists_exact_prescription_provenance(db: Session) -> None:
    user, cycle, prescribed, exercise = _cycle_with_prescription(db)

    feedback = record_workout_cycle_exercise_feedback(
        db,
        user_id=user.id,
        cycle_id=cycle.id,
        workout_plan_exercise_id=prescribed.id,
        feedback_type=WorkoutCycleExerciseFeedbackType.LIKED,
        persistent=True,
        note_optional="Good movement.",
    )

    assert feedback.user_id == user.id
    assert feedback.cycle_id == cycle.id
    assert feedback.workout_plan_exercise_id == prescribed.id
    assert feedback.exercise_id == exercise.id
    assert feedback.feedback_type is WorkoutCycleExerciseFeedbackType.LIKED
    assert feedback.persistent is True
    assert feedback.note_optional == "Good movement."
    assert feedback.created_at is not None
    assert feedback.updated_at is not None


@pytest.mark.parametrize("feedback_type", list(WorkoutCycleExerciseFeedbackType))
def test_every_feedback_type_persists(
    db: Session,
    feedback_type: WorkoutCycleExerciseFeedbackType,
) -> None:
    user, cycle, prescribed, _exercise_row = _cycle_with_prescription(db)

    feedback = record_workout_cycle_exercise_feedback(
        db,
        user_id=user.id,
        cycle_id=cycle.id,
        workout_plan_exercise_id=prescribed.id,
        feedback_type=feedback_type,
        persistent=False,
    )

    assert feedback.feedback_type is feedback_type


@pytest.mark.parametrize("persistent", [False, True])
def test_persistent_is_explicit(db: Session, persistent: bool) -> None:
    user, cycle, prescribed, _exercise_row = _cycle_with_prescription(db)

    feedback = record_workout_cycle_exercise_feedback(
        db,
        user_id=user.id,
        cycle_id=cycle.id,
        workout_plan_exercise_id=prescribed.id,
        feedback_type=WorkoutCycleExerciseFeedbackType.UNCOMFORTABLE,
        persistent=persistent,
    )

    assert feedback.persistent is persistent


def test_feedback_allows_completed_cycle_history(db: Session) -> None:
    user, cycle, prescribed, _exercise_row = _cycle_with_prescription(db)
    cycle.status = WorkoutCycleStatus.COMPLETED
    cycle.completed_at = datetime.now(UTC)
    db.flush()

    feedback = record_workout_cycle_exercise_feedback(
        db,
        user_id=user.id,
        cycle_id=cycle.id,
        workout_plan_exercise_id=prescribed.id,
        feedback_type=WorkoutCycleExerciseFeedbackType.PAIN,
        persistent=False,
    )

    assert feedback.cycle_id == cycle.id


def test_other_user_cannot_record_feedback_for_cycle(db: Session) -> None:
    owner, cycle, prescribed, _exercise_row = _cycle_with_prescription(db)
    other = _user(db, "other-user")

    with pytest.raises(WorkoutCycleExerciseFeedbackPlanExerciseNotFoundError):
        record_workout_cycle_exercise_feedback(
            db,
            user_id=other.id,
            cycle_id=cycle.id,
            workout_plan_exercise_id=prescribed.id,
            feedback_type=WorkoutCycleExerciseFeedbackType.LIKED,
            persistent=False,
        )
    assert owner.id != other.id


def test_exercise_from_another_cycle_is_rejected(db: Session) -> None:
    user, first_cycle, _first_item, _first_exercise = _cycle_with_prescription(db)
    _same_user, _second_cycle, second_item, _second_exercise = _cycle_with_prescription(
        db, user=user, plan_status=WorkoutPlanStatus.SUPERSEDED
    )

    with pytest.raises(WorkoutCycleExerciseFeedbackPlanExerciseNotFoundError):
        record_workout_cycle_exercise_feedback(
            db,
            user_id=user.id,
            cycle_id=first_cycle.id,
            workout_plan_exercise_id=second_item.id,
            feedback_type=WorkoutCycleExerciseFeedbackType.INEFFECTIVE,
            persistent=False,
        )


def test_duplicate_cycle_prescription_feedback_type_is_rejected(db: Session) -> None:
    user, cycle, prescribed, _exercise_row = _cycle_with_prescription(db)
    record_workout_cycle_exercise_feedback(
        db,
        user_id=user.id,
        cycle_id=cycle.id,
        workout_plan_exercise_id=prescribed.id,
        feedback_type=WorkoutCycleExerciseFeedbackType.LIKED,
        persistent=False,
    )

    with pytest.raises(WorkoutCycleExerciseFeedbackDuplicateError):
        record_workout_cycle_exercise_feedback(
            db,
            user_id=user.id,
            cycle_id=cycle.id,
            workout_plan_exercise_id=prescribed.id,
            feedback_type=WorkoutCycleExerciseFeedbackType.LIKED,
            persistent=True,
        )


def test_pain_and_uncomfortable_are_distinct_feedback_events(db: Session) -> None:
    user, cycle, prescribed, _exercise_row = _cycle_with_prescription(db)

    pain = record_workout_cycle_exercise_feedback(
        db,
        user_id=user.id,
        cycle_id=cycle.id,
        workout_plan_exercise_id=prescribed.id,
        feedback_type=WorkoutCycleExerciseFeedbackType.PAIN,
        persistent=False,
    )
    uncomfortable = record_workout_cycle_exercise_feedback(
        db,
        user_id=user.id,
        cycle_id=cycle.id,
        workout_plan_exercise_id=prescribed.id,
        feedback_type=WorkoutCycleExerciseFeedbackType.UNCOMFORTABLE,
        persistent=True,
    )

    assert pain.feedback_type is WorkoutCycleExerciseFeedbackType.PAIN
    assert uncomfortable.feedback_type is WorkoutCycleExerciseFeedbackType.UNCOMFORTABLE
    assert pain.id != uncomfortable.id


def test_optional_note_is_validated_and_persisted(db: Session) -> None:
    with pytest.raises(ValidationError):
        WorkoutCycleExerciseFeedbackInput(
            feedback_type=WorkoutCycleExerciseFeedbackType.LIKED,
            persistent=False,
            note_optional="x" * 1001,
        )

    user, cycle, prescribed, _exercise_row = _cycle_with_prescription(db)
    payload = WorkoutCycleExerciseFeedbackInput(
        feedback_type=WorkoutCycleExerciseFeedbackType.INEFFECTIVE,
        persistent=False,
        note_optional="The target was unclear.",
    )
    feedback = record_workout_cycle_exercise_feedback(
        db,
        user_id=user.id,
        cycle_id=cycle.id,
        workout_plan_exercise_id=prescribed.id,
        feedback_type=payload.feedback_type,
        persistent=payload.persistent,
        note_optional=payload.note_optional,
    )

    assert feedback.note_optional == "The target was unclear."


def test_feedback_model_foreign_keys_reject_unknown_records(db: Session) -> None:
    user, cycle, prescribed, exercise = _cycle_with_prescription(db)
    feedback = WorkoutCycleExerciseFeedback(
        user_id=user.id,
        cycle_id=cycle.id,
        workout_plan_exercise_id=prescribed.id,
        exercise_id=exercise.id,
        feedback_type=WorkoutCycleExerciseFeedbackType.LIKED,
        persistent=False,
    )
    feedback.user_id = UUID(int=0)
    db.add(feedback)

    with pytest.raises(IntegrityError):
        db.flush()
