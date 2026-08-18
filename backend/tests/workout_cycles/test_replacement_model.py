from __future__ import annotations

from uuid import UUID, uuid4

import pytest
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
from app.workout_cycles.enums import (
    WorkoutExerciseReplacementReason,
    WorkoutExerciseReplacementScope,
)
from app.workout_cycles.models import WorkoutCycle, WorkoutExerciseReplacement
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanExercise


def _user(db: Session) -> User:
    user = User(email=f"replacement-{uuid4()}@example.com", password_hash="hash")
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


def _cycle_and_prescription(
    db: Session,
) -> tuple[User, WorkoutCycle, WorkoutPlanExercise, Exercise, Exercise]:
    user = _user(db)
    original = _exercise(db, "original")
    replacement = _exercise(db, "replacement")
    plan = WorkoutPlan(
        user_id=user.id,
        status=WorkoutPlanStatus.ACTIVE,
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
        estimated_duration_minutes=20,
    )
    prescribed = WorkoutPlanExercise(
        exercise_id=original.id,
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
        user_id=user.id,
        workout_plan_id=plan.id,
        duration_weeks=4,
    )
    db.add(cycle)
    db.flush()
    return user, cycle, prescribed, original, replacement


def _replacement(
    user: User,
    cycle: WorkoutCycle,
    prescribed: WorkoutPlanExercise,
    original: Exercise,
    replacement: Exercise,
    *,
    reason: WorkoutExerciseReplacementReason = WorkoutExerciseReplacementReason.DISLIKE,
    scope: WorkoutExerciseReplacementScope = WorkoutExerciseReplacementScope.THIS_TIME,
    week_number: int = 2,
) -> WorkoutExerciseReplacement:
    return WorkoutExerciseReplacement(
        user_id=user.id,
        cycle_id=cycle.id,
        workout_plan_exercise_id=prescribed.id,
        original_exercise_id=original.id,
        replacement_exercise_id=replacement.id,
        reason=reason,
        scope=scope,
        week_number=week_number,
    )


def test_valid_replacement_persists_with_ownership_history(db: Session) -> None:
    user, cycle, prescribed, original, replacement = _cycle_and_prescription(db)
    record = _replacement(user, cycle, prescribed, original, replacement)

    db.add(record)
    db.flush()

    saved = db.get(WorkoutExerciseReplacement, record.id)
    assert saved is not None
    assert saved.user_id == user.id
    assert saved.cycle_id == cycle.id
    assert saved.workout_plan_exercise_id == prescribed.id
    assert saved.original_exercise_id == original.id
    assert saved.replacement_exercise_id == replacement.id
    assert saved.created_at is not None


@pytest.mark.parametrize("reason", list(WorkoutExerciseReplacementReason))
def test_replacement_accepts_every_supported_reason(
    db: Session,
    reason: WorkoutExerciseReplacementReason,
) -> None:
    user, cycle, prescribed, original, replacement = _cycle_and_prescription(db)
    record = _replacement(user, cycle, prescribed, original, replacement, reason=reason)

    db.add(record)
    db.flush()

    assert record.reason is reason


@pytest.mark.parametrize("scope", list(WorkoutExerciseReplacementScope))
def test_replacement_accepts_both_scopes(
    db: Session,
    scope: WorkoutExerciseReplacementScope,
) -> None:
    user, cycle, prescribed, original, replacement = _cycle_and_prescription(db)
    record = _replacement(user, cycle, prescribed, original, replacement, scope=scope)

    db.add(record)
    db.flush()

    assert record.scope is scope


@pytest.mark.parametrize("week_number", [0, 9])
def test_replacement_rejects_week_outside_cycle_bounds(
    db: Session,
    week_number: int,
) -> None:
    user, cycle, prescribed, original, replacement = _cycle_and_prescription(db)
    record = _replacement(
        user,
        cycle,
        prescribed,
        original,
        replacement,
        week_number=week_number,
    )
    db.add(record)

    with pytest.raises(IntegrityError, match="week_number"):
        db.flush()


def test_replacement_rejects_same_original_and_replacement_exercise(db: Session) -> None:
    user, cycle, prescribed, original, _replacement_exercise = _cycle_and_prescription(db)
    record = _replacement(user, cycle, prescribed, original, original)
    db.add(record)

    with pytest.raises(IntegrityError, match="distinct"):
        db.flush()


@pytest.mark.parametrize(
    "field",
    [
        "user_id",
        "cycle_id",
        "workout_plan_exercise_id",
        "original_exercise_id",
        "replacement_exercise_id",
    ],
)
def test_replacement_foreign_keys_reject_unknown_records(
    db: Session,
    field: str,
) -> None:
    user, cycle, prescribed, original, replacement = _cycle_and_prescription(db)
    record = _replacement(user, cycle, prescribed, original, replacement)
    setattr(record, field, UUID(int=0))
    db.add(record)

    with pytest.raises(IntegrityError):
        db.flush()
