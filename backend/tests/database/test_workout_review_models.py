from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.workout_reviews.enums import WorkoutReviewStatus
from app.workout_reviews.models import WorkoutPlanReview
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutPlan


def _active_plan(db: Session, *, email: str) -> WorkoutPlan:
    user = User(email=email, password_hash="hash")
    db.add(user)
    db.flush()
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
        generation_method="ai",
    )
    db.add(plan)
    db.flush()
    return plan


def test_workout_review_defaults_to_pending_with_revision_one(db: Session) -> None:
    plan = _active_plan(db, email=f"review-default-{uuid4()}@example.com")

    review = WorkoutPlanReview(source_plan_id=plan.id, user_id=plan.user_id)
    db.add(review)
    db.flush()

    assert review.status is WorkoutReviewStatus.PENDING
    assert review.draft_revision == 1
    assert review.claimed_by_user_id is None
    assert review.approved_plan_id is None


def test_only_one_workout_review_can_exist_for_a_source_plan(db: Session) -> None:
    plan = _active_plan(db, email=f"review-unique-{uuid4()}@example.com")
    db.add(WorkoutPlanReview(source_plan_id=plan.id, user_id=plan.user_id))
    db.flush()
    db.add(WorkoutPlanReview(source_plan_id=plan.id, user_id=plan.user_id))

    with pytest.raises(IntegrityError):
        db.flush()
