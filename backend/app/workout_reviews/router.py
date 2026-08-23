from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.cookies import require_trusted_origin
from app.exercises.enums import ExerciseContentType
from app.profile.models import UserProfile
from app.workout_reviews.coach_quality import build_coach_quality_projection
from app.workout_reviews.dependencies import (
    CoachUser,
    DatabaseSession,
    WorkoutReviewServiceDependency,
)
from app.workout_reviews.enums import WorkoutReviewErrorCode, WorkoutReviewQueueView
from app.workout_reviews.models import WorkoutPlanReview
from app.workout_reviews.repository import get_exercises
from app.workout_reviews.schemas import (
    WorkoutReviewAccessResponse,
    WorkoutReviewApproveRequest,
    WorkoutReviewDetailResponse,
    WorkoutReviewDraftUpdate,
    WorkoutReviewExerciseOption,
    WorkoutReviewQueueItemResponse,
)
from app.workout_reviews.service import ReviewConflict
from app.workout_reviews.summary import (
    build_fitsho_recommendation,
    build_review_athlete_summary,
)
from app.workout_reviews.template_selection import build_coach_template_selection
from app.workout_reviews.validation import DraftValidationError
from app.workouts.router import to_plan_response

router = APIRouter(prefix="/api/v1/coach/workout-reviews", tags=["coach-workout-reviews"])


@router.get("/access", response_model=WorkoutReviewAccessResponse)
def read_access(_coach: CoachUser) -> WorkoutReviewAccessResponse:
    return WorkoutReviewAccessResponse()


@router.get("", response_model=list[WorkoutReviewQueueItemResponse])
def read_queue(
    service: WorkoutReviewServiceDependency,
    coach: CoachUser,
    db: DatabaseSession,
    view: WorkoutReviewQueueView = WorkoutReviewQueueView.PENDING,
) -> list[WorkoutReviewQueueItemResponse]:
    return [_queue_response(db, review) for review in service.queue(view, coach.id)]


@router.get("/{review_id}", response_model=WorkoutReviewDetailResponse)
def read_review(
    review_id: UUID,
    service: WorkoutReviewServiceDependency,
    _coach: CoachUser,
    db: DatabaseSession,
) -> WorkoutReviewDetailResponse:
    return _detail_response(db, _service_call(lambda: service.detail(review_id)))


@router.post(
    "/{review_id}/claim",
    response_model=WorkoutReviewDetailResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def claim_review(
    review_id: UUID,
    service: WorkoutReviewServiceDependency,
    coach: CoachUser,
    db: DatabaseSession,
) -> WorkoutReviewDetailResponse:
    review = _service_call(lambda: service.claim(review_id, coach.id))
    return _detail_response(db, review)


@router.post(
    "/{review_id}/renew",
    response_model=WorkoutReviewDetailResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def renew_review(
    review_id: UUID,
    service: WorkoutReviewServiceDependency,
    coach: CoachUser,
    db: DatabaseSession,
) -> WorkoutReviewDetailResponse:
    review = _service_call(lambda: service.renew(review_id, coach.id))
    return _detail_response(db, review)


@router.put(
    "/{review_id}/draft",
    response_model=WorkoutReviewDetailResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def save_review_draft(
    review_id: UUID,
    payload: WorkoutReviewDraftUpdate,
    service: WorkoutReviewServiceDependency,
    coach: CoachUser,
    db: DatabaseSession,
) -> WorkoutReviewDetailResponse:
    try:
        review = service.save_draft(review_id, coach.id, payload)
    except DraftValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": error.code.value, "problems": error.problems},
        ) from error
    except ReviewConflict as error:
        raise _http_conflict(error) from error
    return _detail_response(db, review)


@router.post(
    "/{review_id}/approve",
    response_model=WorkoutReviewDetailResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def approve_review(
    review_id: UUID,
    payload: WorkoutReviewApproveRequest,
    service: WorkoutReviewServiceDependency,
    coach: CoachUser,
    db: DatabaseSession,
) -> WorkoutReviewDetailResponse:
    try:
        service.approve(
            review_id,
            coach.id,
            expected_revision=payload.expected_revision,
        )
        review = service.detail(review_id)
    except DraftValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": error.code.value, "problems": error.problems},
        ) from error
    except ReviewConflict as error:
        raise _http_conflict(error) from error
    return _detail_response(db, review)


def _service_call(operation: Callable[[], WorkoutPlanReview]) -> WorkoutPlanReview:
    try:
        return operation()
    except ReviewConflict as error:
        raise _http_conflict(error) from error


def _http_conflict(error: ReviewConflict) -> HTTPException:
    status_code = (
        status.HTTP_404_NOT_FOUND
        if error.code is WorkoutReviewErrorCode.REVIEW_NOT_FOUND
        else status.HTTP_409_CONFLICT
    )
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code.value, "message": str(error)},
    )


def _queue_response(db: Session, review: WorkoutPlanReview) -> WorkoutReviewQueueItemResponse:
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == review.user_id))
    snapshot = review.source_plan.profile_snapshot
    return WorkoutReviewQueueItemResponse(
        id=review.id,
        source_plan_id=review.source_plan_id,
        user_id=review.user_id,
        member_display_name=profile.display_name if profile else None,
        fitness_goal=_optional_text(snapshot.get("goal") or snapshot.get("fitness_goal")),
        experience_level=_optional_text(snapshot.get("experience_level")),
        status=review.status,
        claimed_by_user_id=review.claimed_by_user_id,
        lease_expires_at=review.lease_expires_at,
        draft_revision=review.draft_revision,
        created_at=review.created_at,
        approved_at=review.approved_at,
    )


def _detail_response(db: Session, review: WorkoutPlanReview) -> WorkoutReviewDetailResponse:
    summary = _queue_response(db, review)
    catalog = review.source_plan.exercise_catalog_snapshot.get("exercises")
    candidate_ids = (
        {UUID(value) for value in catalog if _uuid_text(value) is not None}
        if isinstance(catalog, dict)
        else set()
    )
    options = [
        WorkoutReviewExerciseOption(
            id=item.id,
            name_en=item.name_en,
            name_fa=item.name_fa,
            prescription_mode=item.prescription_mode,
            duration_min_seconds=item.duration_min_seconds,
            duration_max_seconds=item.duration_max_seconds,
        )
        for item in sorted(get_exercises(db, candidate_ids), key=lambda exercise: exercise.name_en)
        if (
            item.is_active
            and item.is_programmable
            and not item.needs_review
            and item.content_type is ExerciseContentType.EXERCISE
        )
    ]
    return WorkoutReviewDetailResponse(
        **summary.model_dump(),
        coach_note=review.coach_note,
        draft=review.draft_payload,
        source_plan=to_plan_response(review.source_plan, db=db).model_dump(mode="json"),
        exercise_options=options,
        athlete_summary=build_review_athlete_summary(db, review),
        fitsho_recommendation=build_fitsho_recommendation(db, review),
        template_selection=build_coach_template_selection(review.source_plan.decision_trace),
        coach_quality_metrics=build_coach_quality_projection(review.source_plan.decision_trace),
    )


def _optional_text(value: object) -> str | None:
    return str(value) if value is not None else None


def _uuid_text(value: object) -> str | None:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError):
        return None
