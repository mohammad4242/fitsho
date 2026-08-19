from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.athlete_state.schemas import AthleteState
from app.athlete_state.service import AthleteStateBuilder
from app.workout_reviews.models import WorkoutPlanReview
from app.workout_reviews.schemas import WorkoutReviewAthleteSummary


def build_athlete_summary(
    state: AthleteState,
    *,
    previous_approved_plan_id: UUID | None,
) -> WorkoutReviewAthleteSummary:
    """Map the already-derived state into the coach-review response contract."""
    return WorkoutReviewAthleteSummary(
        athlete_state=state,
        previous_approved_plan_id=previous_approved_plan_id,
    )


def build_review_athlete_summary(
    db: Session,
    review: WorkoutPlanReview,
) -> WorkoutReviewAthleteSummary:
    state = AthleteStateBuilder(db).build(review.user_id)
    return build_athlete_summary(
        state,
        previous_approved_plan_id=review.source_plan.previous_program_id,
    )
