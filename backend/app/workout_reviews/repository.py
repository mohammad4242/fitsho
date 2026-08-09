from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.exercises.models import Exercise
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
    return list(db.scalars(select(Exercise).where(Exercise.id.in_(exercise_ids))).all())
