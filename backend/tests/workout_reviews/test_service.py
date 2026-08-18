from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
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
from app.workout_reviews.enums import WorkoutReviewErrorCode, WorkoutReviewStatus
from app.workout_reviews.models import WorkoutPlanReview
from app.workout_reviews.repository import ensure_pending_review
from app.workout_reviews.schemas import WorkoutReviewDraftUpdate
from app.workout_reviews.service import ReviewConflict, WorkoutReviewService
from app.workout_reviews.validation import DraftValidationError
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanExercise


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 9, 8, 30, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, *, minutes: int) -> None:
        self.now += timedelta(minutes=minutes)


def _user(db: Session, prefix: str) -> User:
    user = User(email=f"{prefix}-{uuid4()}@example.com", password_hash="hash")
    db.add(user)
    db.flush()
    return user


def _exercise(db: Session, slug: str, *, programmable: bool = True) -> Exercise:
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
        is_programmable=programmable,
        needs_review=False,
    )
    db.add(exercise)
    db.flush()
    return exercise


def _candidate_snapshot(exercise: Exercise) -> dict[str, object]:
    return {
        "id": str(exercise.id),
        "primary_muscle": exercise.primary_muscle.value if exercise.primary_muscle else None,
        "secondary_muscles": [],
        "movement_pattern": exercise.movement_pattern.value,
        "exercise_type": exercise.exercise_type.value,
        "equipment": [],
        "difficulty": exercise.difficulty.value,
        "caution_tags": [],
        "labels": [],
    }


def _active_plan(
    db: Session,
    *,
    user: User,
    exercises: list[Exercise],
    status: WorkoutPlanStatus = WorkoutPlanStatus.ACTIVE,
) -> WorkoutPlan:
    plan = WorkoutPlan(
        user_id=user.id,
        status=status,
        generation_signature="a" * 64,
        profile_snapshot={"plan_duration_weeks": 4, "session_duration_minutes": 45},
        provider="fake",
        model_id="fake-model",
        prompt_version="v1",
        generation_policy_version="v1",
        candidate_set_hash="b" * 64,
        generation_method="ai",
        exercise_catalog_snapshot={
            "exercises": {
                str(exercise.id): _candidate_snapshot(exercise) for exercise in exercises
            }
        },
    )
    day = WorkoutDay(
        day_number=1,
        title_en="Upper body",
        title_fa="بالاتنه",
        estimated_duration_minutes=20,
    )
    day.exercises.append(
        WorkoutPlanExercise(
            exercise_id=exercises[0].id,
            order_index=1,
            sets=3,
            reps_min=8,
            reps_max=12,
            rest_seconds=90,
            rir=2,
            estimated_minutes=5,
            notes_en=None,
            notes_fa=None,
            exercise_snapshot=_candidate_snapshot(exercises[0]),
        )
    )
    plan.days.append(day)
    db.add(plan)
    db.flush()
    return plan


def _draft(
    review: WorkoutPlanReview,
    *,
    exercise_id: str | None = None,
) -> WorkoutReviewDraftUpdate:
    assert review.draft_payload is not None
    payload = deepcopy(review.draft_payload)
    payload["expected_revision"] = review.draft_revision
    if exercise_id is not None:
        payload["days"][0]["exercises"][0]["exercise_id"] = exercise_id
    return WorkoutReviewDraftUpdate.model_validate(payload)


def test_ensure_pending_review_is_idempotent(db: Session) -> None:
    member = _user(db, "idempotent-member")
    exercise = _exercise(db, "press")
    plan = _active_plan(db, user=member, exercises=[exercise])

    first = ensure_pending_review(db, plan)
    second = ensure_pending_review(db, plan)

    assert first.id == second.id
    assert db.scalars(select(WorkoutPlanReview)).all() == [first]


def test_claim_rejects_second_coach_until_lease_expires(db: Session) -> None:
    member = _user(db, "lease-member")
    first_coach = _user(db, "first-coach")
    second_coach = _user(db, "second-coach")
    exercise = _exercise(db, "row")
    review = ensure_pending_review(db, _active_plan(db, user=member, exercises=[exercise]))
    clock = Clock()
    service = WorkoutReviewService(db, clock=clock)

    service.claim(review.id, first_coach.id)
    with pytest.raises(ReviewConflict) as error:
        service.claim(review.id, second_coach.id)
    assert error.value.code is WorkoutReviewErrorCode.REVIEW_ALREADY_CLAIMED

    clock.advance(minutes=31)
    claimed = service.claim(review.id, second_coach.id)

    assert claimed.claimed_by_user_id == second_coach.id
    assert claimed.status is WorkoutReviewStatus.CLAIMED


def test_save_rejects_stale_revision_and_preserves_draft(db: Session) -> None:
    member = _user(db, "stale-member")
    coach = _user(db, "stale-coach")
    exercise = _exercise(db, "squat")
    review = ensure_pending_review(db, _active_plan(db, user=member, exercises=[exercise]))
    service = WorkoutReviewService(db, clock=Clock())
    service.claim(review.id, coach.id)
    original = deepcopy(review.draft_payload)
    payload = _draft(review)
    payload.expected_revision -= 1

    with pytest.raises(ReviewConflict) as error:
        service.save_draft(review.id, coach.id, payload)

    assert error.value.code is WorkoutReviewErrorCode.STALE_DRAFT_REVISION
    assert review.draft_payload == original


def test_save_rejects_exercise_outside_source_snapshot(db: Session) -> None:
    member = _user(db, "outside-member")
    coach = _user(db, "outside-coach")
    allowed = _exercise(db, "allowed")
    outside = _exercise(db, "outside")
    review = ensure_pending_review(db, _active_plan(db, user=member, exercises=[allowed]))
    service = WorkoutReviewService(db, clock=Clock())
    service.claim(review.id, coach.id)

    with pytest.raises(DraftValidationError) as error:
        service.save_draft(review.id, coach.id, _draft(review, exercise_id=str(outside.id)))

    assert error.value.problems[0]["code"] == WorkoutReviewErrorCode.EXERCISE_NOT_ALLOWED.value


def test_approval_creates_new_active_version_and_preserves_source(db: Session) -> None:
    member = _user(db, "approval-member")
    coach = _user(db, "approval-coach")
    original_exercise = _exercise(db, "original")
    replacement = _exercise(db, "replacement")
    source = _active_plan(db, user=member, exercises=[original_exercise, replacement])
    review = ensure_pending_review(db, source)
    service = WorkoutReviewService(db, clock=Clock())
    service.claim(review.id, coach.id)
    payload = _draft(review, exercise_id=str(replacement.id))
    payload.days[0].exercises[0].sets = 4
    saved = service.save_draft(review.id, coach.id, payload)
    source_payload = deepcopy(saved.source_plan.days[0].exercises[0].exercise_snapshot)

    approved = service.approve(
        review.id,
        coach.id,
        expected_revision=saved.draft_revision,
    )

    db.refresh(source)
    db.refresh(review)
    assert source.status is WorkoutPlanStatus.SUPERSEDED
    assert source.days[0].exercises[0].exercise_id == original_exercise.id
    assert source.days[0].exercises[0].exercise_snapshot == source_payload
    assert approved.status is WorkoutPlanStatus.ACTIVE
    assert approved.previous_program_id == source.id
    assert approved.days[0].exercises[0].exercise_id == replacement.id
    assert approved.days[0].exercises[0].sets == 4
    assert review.approved_plan_id == approved.id
    assert review.status is WorkoutReviewStatus.APPROVED


def test_approval_activates_pending_plan_without_creating_review_loop(db: Session) -> None:
    member = _user(db, "pending-approval-member")
    coach = _user(db, "pending-approval-coach")
    exercise = _exercise(db, "pending-press")
    source = _active_plan(
        db,
        user=member,
        exercises=[exercise],
        status=WorkoutPlanStatus.PENDING_REVIEW,
    )
    review = ensure_pending_review(db, source)
    service = WorkoutReviewService(db, clock=Clock())
    service.claim(review.id, coach.id)
    saved = service.save_draft(review.id, coach.id, _draft(review))

    approved = service.approve(
        review.id,
        coach.id,
        expected_revision=saved.draft_revision,
    )

    db.refresh(source)
    db.refresh(review)
    assert source.status is WorkoutPlanStatus.SUPERSEDED
    assert approved.status is WorkoutPlanStatus.ACTIVE
    assert approved.activated_at == Clock().now
    assert review.status is WorkoutReviewStatus.APPROVED
    assert review.approved_plan_id == approved.id
    assert (
        db.query(WorkoutPlanReview)
        .filter(WorkoutPlanReview.source_plan_id == approved.id)
        .count()
        == 0
    )


def test_approval_supersedes_previous_active_plan_only_at_approval(db: Session) -> None:
    member = _user(db, "approval-transition-member")
    coach = _user(db, "approval-transition-coach")
    previous_exercise = _exercise(db, "previous-press")
    pending_exercise = _exercise(db, "pending-press")
    previous = _active_plan(db, user=member, exercises=[previous_exercise])
    source = _active_plan(
        db,
        user=member,
        exercises=[pending_exercise],
        status=WorkoutPlanStatus.PENDING_REVIEW,
    )
    review = ensure_pending_review(db, source)
    service = WorkoutReviewService(db, clock=Clock())
    service.claim(review.id, coach.id)
    saved = service.save_draft(review.id, coach.id, _draft(review))

    assert previous.status is WorkoutPlanStatus.ACTIVE

    approved = service.approve(
        review.id,
        coach.id,
        expected_revision=saved.draft_revision,
    )

    db.refresh(previous)
    assert previous.status is WorkoutPlanStatus.SUPERSEDED
    assert previous.superseded_at == Clock().now
    assert approved.status is WorkoutPlanStatus.ACTIVE
    assert approved.activated_at == Clock().now
    assert (
        db.query(WorkoutPlan)
        .filter(
            WorkoutPlan.user_id == member.id,
            WorkoutPlan.status == WorkoutPlanStatus.ACTIVE,
        )
        .count()
        == 1
    )


def test_approval_cannot_replace_a_newer_active_plan(db: Session) -> None:
    member = _user(db, "newer-member")
    coach = _user(db, "newer-coach")
    exercise = _exercise(db, "deadlift")
    source = _active_plan(db, user=member, exercises=[exercise])
    review = ensure_pending_review(db, source)
    service = WorkoutReviewService(db, clock=Clock())
    service.claim(review.id, coach.id)
    source.status = WorkoutPlanStatus.SUPERSEDED
    newer = _active_plan(db, user=member, exercises=[exercise])
    db.flush()

    with pytest.raises(ReviewConflict) as error:
        service.approve(review.id, coach.id, expected_revision=review.draft_revision)

    assert error.value.code is WorkoutReviewErrorCode.REVIEW_SUPERSEDED
    assert newer.status is WorkoutPlanStatus.ACTIVE
