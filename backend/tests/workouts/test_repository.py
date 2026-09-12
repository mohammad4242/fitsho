from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.workouts.repository as workout_repository
from app.auth.models import User
from app.workout_reviews.enums import WorkoutReviewStatus
from app.workout_reviews.models import WorkoutPlanReview
from app.workouts.enums import WorkoutGenerationStatus, WorkoutPlanStatus
from app.workouts.models import WorkoutPlan
from app.workouts.repository import (
    activate_plan,
    create_generation,
    get_active_plan,
    persist_pending_review_plan,
)


def make_user(db: Session) -> User:
    user = User(email="repository@example.com", password_hash="hash")
    db.add(user)
    db.flush()
    return user


def new_plan(user_id: UUID, signature: str) -> WorkoutPlan:
    return WorkoutPlan(
        user_id=user_id,
        status=WorkoutPlanStatus.SUPERSEDED,
        generation_signature=signature,
        profile_snapshot={"plan_duration_weeks": 4},
        provider="fake",
        model_id="fake-model",
        prompt_version="v1",
        generation_policy_version="v1",
        candidate_set_hash="b" * 64,
        generation_method="ai",
    )


def test_workout_plan_status_includes_pending_review() -> None:
    assert "pending_review" in {status.value for status in WorkoutPlanStatus}


def test_pending_review_workout_plan_status_persists(db: Session) -> None:
    user = make_user(db)
    plan = new_plan(user.id, "a" * 64)
    plan.status = WorkoutPlanStatus.PENDING_REVIEW

    db.add(plan)
    db.flush()
    db.expire(plan)

    assert db.get(WorkoutPlan, plan.id).status is WorkoutPlanStatus.PENDING_REVIEW


def test_activate_plan_supersedes_previous_active_plan(db: Session) -> None:
    user = make_user(db)
    previous = new_plan(user.id, "a" * 64)
    previous.status = WorkoutPlanStatus.ACTIVE
    db.add(previous)
    db.flush()
    generation = create_generation(
        db,
        user_id=user.id,
        provider="fake",
        model_id="fake-model",
        candidate_count=1,
    )
    replacement = new_plan(user.id, "c" * 64)

    activate_plan(db, replacement, generation)

    assert previous.status is WorkoutPlanStatus.SUPERSEDED
    assert replacement.status is WorkoutPlanStatus.ACTIVE
    assert generation.status is WorkoutGenerationStatus.SUCCEEDED
    assert get_active_plan(db, user.id) is replacement


def test_activate_plan_creates_review_and_supersedes_previous_open_review(db: Session) -> None:
    user = make_user(db)
    previous = new_plan(user.id, "a" * 64)
    previous.status = WorkoutPlanStatus.ACTIVE
    db.add(previous)
    db.flush()
    previous_review = WorkoutPlanReview(source_plan=previous, user_id=user.id)
    db.add(previous_review)
    generation = create_generation(
        db,
        user_id=user.id,
        provider="fake",
        model_id="fake-model",
        candidate_count=1,
    )
    replacement = new_plan(user.id, "c" * 64)

    activate_plan(db, replacement, generation)

    replacement_review = db.scalar(
        select(WorkoutPlanReview).where(WorkoutPlanReview.source_plan_id == replacement.id)
    )
    assert previous_review.status is WorkoutReviewStatus.SUPERSEDED
    assert replacement_review is not None
    assert replacement_review.status is WorkoutReviewStatus.PENDING


def test_persist_pending_review_plan_keeps_previous_active_plan(db: Session) -> None:
    user = make_user(db)
    previous = new_plan(user.id, "a" * 64)
    previous.status = WorkoutPlanStatus.ACTIVE
    previous_review = WorkoutPlanReview(source_plan=previous, user_id=user.id)
    db.add(previous)
    db.add(previous_review)
    db.flush()
    generation = create_generation(
        db,
        user_id=user.id,
        provider="fake",
        model_id="fake-model",
        candidate_count=1,
    )
    replacement = new_plan(user.id, "c" * 64)

    persist_pending_review_plan(db, replacement, generation)

    foreground = list(
        db.scalars(
            select(WorkoutPlan).where(
                WorkoutPlan.user_id == user.id,
                WorkoutPlan.status.in_(
                    [WorkoutPlanStatus.ACTIVE, WorkoutPlanStatus.PENDING_REVIEW]
                ),
            )
        ).all()
    )
    review = db.scalar(
        select(WorkoutPlanReview).where(WorkoutPlanReview.source_plan_id == replacement.id)
    )
    assert previous.status is WorkoutPlanStatus.ACTIVE
    assert previous.superseded_at is None
    assert previous_review.status is WorkoutReviewStatus.PENDING
    assert replacement.status is WorkoutPlanStatus.PENDING_REVIEW
    assert replacement.activated_at is None
    assert {plan.id for plan in foreground} == {previous.id, replacement.id}
    assert workout_repository.get_current_foreground_plan(db, user.id) is replacement
    assert review is not None
    assert review.status is WorkoutReviewStatus.PENDING


def test_persist_pending_review_plan_supersedes_previous_pending_review_and_open_review(
    db: Session,
) -> None:
    user = make_user(db)
    previous = new_plan(user.id, "a" * 64)
    previous.status = WorkoutPlanStatus.PENDING_REVIEW
    previous_review = WorkoutPlanReview(source_plan=previous, user_id=user.id)
    db.add_all([previous, previous_review])
    db.flush()
    generation = create_generation(
        db,
        user_id=user.id,
        provider="fake",
        model_id="fake-model",
        candidate_count=1,
    )
    replacement = new_plan(user.id, "c" * 64)

    persist_pending_review_plan(db, replacement, generation)

    assert previous.status is WorkoutPlanStatus.SUPERSEDED
    assert previous.superseded_at is not None
    assert previous_review.status is WorkoutReviewStatus.SUPERSEDED
    assert replacement.status is WorkoutPlanStatus.PENDING_REVIEW
    current_foreground_plan = getattr(workout_repository, "get_current_foreground_plan", None)
    assert callable(current_foreground_plan)
    if callable(current_foreground_plan):
        assert current_foreground_plan(db, user.id) is replacement


def test_persist_pending_review_plan_keeps_active_and_cleans_up_pending_plans(
    db: Session,
) -> None:
    user = make_user(db)
    active = new_plan(user.id, "a" * 64)
    active.status = WorkoutPlanStatus.ACTIVE
    pending = new_plan(user.id, "b" * 64)
    pending.status = WorkoutPlanStatus.PENDING_REVIEW
    pending_review = WorkoutPlanReview(source_plan=pending, user_id=user.id)
    db.add_all([active, pending, pending_review])
    db.flush()
    generation = create_generation(
        db,
        user_id=user.id,
        provider="fake",
        model_id="fake-model",
        candidate_count=1,
    )
    replacement = new_plan(user.id, "c" * 64)

    persist_pending_review_plan(db, replacement, generation)

    foreground = list(
        db.scalars(
            select(WorkoutPlan).where(
                WorkoutPlan.user_id == user.id,
                WorkoutPlan.status.in_(
                    [WorkoutPlanStatus.ACTIVE, WorkoutPlanStatus.PENDING_REVIEW]
                ),
            )
        ).all()
    )
    assert active.status is WorkoutPlanStatus.ACTIVE
    assert active.superseded_at is None
    assert pending.status is WorkoutPlanStatus.SUPERSEDED
    assert pending_review.status is WorkoutReviewStatus.SUPERSEDED
    assert replacement.status is WorkoutPlanStatus.PENDING_REVIEW
    assert {plan.id for plan in foreground} == {active.id, replacement.id}
