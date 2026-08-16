from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.exercises.enums import ExerciseContentType
from app.exercises.models import Exercise
from app.workout_reviews.enums import WorkoutReviewQueueView, WorkoutReviewStatus
from app.workout_reviews.models import WorkoutPlanReview
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanExercise


def ensure_pending_review(db: Session, plan: WorkoutPlan) -> WorkoutPlanReview:
    existing = db.scalar(
        select(WorkoutPlanReview).where(WorkoutPlanReview.source_plan_id == plan.id)
    )
    if existing is not None:
        return existing
    review = WorkoutPlanReview(source_plan=plan, user_id=plan.user_id)
    db.add(review)
    db.flush()
    return review


def get_review(db: Session, review_id: UUID) -> WorkoutPlanReview | None:
    return db.scalar(
        select(WorkoutPlanReview)
        .where(WorkoutPlanReview.id == review_id)
        .options(
            selectinload(WorkoutPlanReview.source_plan)
            .selectinload(WorkoutPlan.days)
            .selectinload(WorkoutDay.exercises)
            .selectinload(WorkoutPlanExercise.exercise),
            selectinload(WorkoutPlanReview.approved_plan)
            .selectinload(WorkoutPlan.days)
            .selectinload(WorkoutDay.exercises)
            .selectinload(WorkoutPlanExercise.exercise),
        )
    )


def get_review_for_update(db: Session, review_id: UUID) -> WorkoutPlanReview | None:
    review = db.scalar(
        select(WorkoutPlanReview)
        .where(WorkoutPlanReview.id == review_id)
        .with_for_update()
    )
    if review is None:
        return None
    # Load immutable plan trees in separate SELECTs so PostgreSQL does not lock nullable joins.
    return get_review(db, review.id)


def get_active_plan_for_update(db: Session, user_id: UUID) -> WorkoutPlan | None:
    return db.scalar(
        select(WorkoutPlan)
        .where(WorkoutPlan.user_id == user_id, WorkoutPlan.status == "active")
        .with_for_update()
    )


def get_exercises(db: Session, exercise_ids: set[UUID]) -> list[Exercise]:
    if not exercise_ids:
        return []
    return list(
        db.scalars(
            select(Exercise).where(
                Exercise.id.in_(exercise_ids),
                Exercise.content_type == ExerciseContentType.EXERCISE,
            )
        ).all()
    )


def list_reviews(
    db: Session,
    *,
    view: WorkoutReviewQueueView,
    coach_id: UUID,
    now: datetime,
) -> list[WorkoutPlanReview]:
    statement = select(WorkoutPlanReview).options(
        selectinload(WorkoutPlanReview.source_plan)
    )
    if view is WorkoutReviewQueueView.PENDING:
        statement = statement.where(
            (WorkoutPlanReview.status == WorkoutReviewStatus.PENDING)
            | (
                (WorkoutPlanReview.status == WorkoutReviewStatus.CLAIMED)
                & (WorkoutPlanReview.lease_expires_at <= now)
            )
        )
    elif view is WorkoutReviewQueueView.MINE:
        statement = statement.where(
            WorkoutPlanReview.status == WorkoutReviewStatus.CLAIMED,
            WorkoutPlanReview.claimed_by_user_id == coach_id,
        )
    else:
        statement = statement.where(WorkoutPlanReview.status == WorkoutReviewStatus.APPROVED)
    return list(db.scalars(statement.order_by(WorkoutPlanReview.created_at.asc())).all())


def supersede_open_review(db: Session, plan_id: UUID) -> None:
    review = db.scalar(
        select(WorkoutPlanReview)
        .where(
            WorkoutPlanReview.source_plan_id == plan_id,
            WorkoutPlanReview.status.in_(
                [WorkoutReviewStatus.PENDING, WorkoutReviewStatus.CLAIMED]
            ),
        )
        .with_for_update()
    )
    if review is not None:
        review.status = WorkoutReviewStatus.SUPERSEDED
