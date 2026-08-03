from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.dependencies import AdminUser, require_admin
from app.auth.cookies import require_trusted_origin
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.body_analysis.api_schemas import (
    BodyAnalysisResponse,
    BodyAnalysisResultVersionResponse,
    BodyAnalysisReviewDetail,
    BodyAnalysisReviewHistoryResponse,
    SpecialistReviewRequest,
    SpecialistReviewResponse,
    SpecialistReviewState,
)
from app.body_analysis.enums import BodyAnalysisReviewerRole, BodyAnalysisStatus
from app.body_analysis.models import BodyAnalysis, BodyAnalysisResultVersion, BodyAnalysisReview
from app.body_analysis.runtime import (
    BodyAnalysisRuntimeDependency,
)
from app.body_analysis.schemas import BodyPhotoPreflight
from app.body_analysis.service import (
    BodyAnalysisNotFoundError,
    BodyAnalysisService,
    BodyAnalysisStateError,
    ReviewSubmission,
)
from app.database.session import get_db

router = APIRouter(prefix="/api/v1/body-photo-sessions", tags=["body-analysis"])
review_router = APIRouter(
    prefix="/api/v1/reviews/body-analyses",
    tags=["body-analysis-reviews"],
    dependencies=[Depends(require_admin)],
)
admin_router = APIRouter(
    prefix="/api/v1/admin/body-analyses",
    tags=["admin-body-analyses"],
    dependencies=[Depends(require_admin)],
)

DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Body analysis not found")


def _response(db: Session, analysis: BodyAnalysis) -> BodyAnalysisResponse:
    current = db.scalar(
        select(BodyAnalysisResultVersion)
        .where(BodyAnalysisResultVersion.analysis_id == analysis.id)
        .order_by(BodyAnalysisResultVersion.version.desc())
        .limit(1)
    )
    reviews: list[BodyAnalysisReview] = []
    if current is not None:
        reviews = list(
            db.scalars(
                select(BodyAnalysisReview)
                .where(
                    BodyAnalysisReview.analysis_id == analysis.id,
                    BodyAnalysisReview.result_version_id == current.id,
                )
                .order_by(BodyAnalysisReview.created_at, BodyAnalysisReview.id)
            ).all()
        )
    latest = {item.reviewer_role: item for item in reviews}

    def review_state(role: BodyAnalysisReviewerRole) -> SpecialistReviewState:
        review = latest.get(role)
        return SpecialistReviewState(
            role=role,
            decision=review.decision if review else None,
            reviewed_at=review.created_at if review else None,
            reviewed_result_version=current.version if review and current else None,
        )

    coach = review_state(BodyAnalysisReviewerRole.COACH)
    doctor = review_state(BodyAnalysisReviewerRole.DOCTOR)
    fully_reviewed = (
        coach.decision is not None
        and coach.decision.value == "approved"
        and doctor.decision is not None
        and doctor.decision.value == "approved"
    )
    photo_validation = None
    if isinstance(analysis.raw_result, dict):
        payload = analysis.raw_result.get("photo_validation")
        if isinstance(payload, dict):
            try:
                photo_validation = BodyPhotoPreflight.model_validate(payload)
            except ValueError:
                photo_validation = None
    return BodyAnalysisResponse(
        id=analysis.id,
        session_id=analysis.session_id,
        revision=analysis.revision,
        status=analysis.status,
        provider=analysis.provider,
        model_id=analysis.model_id,
        schema_version=analysis.schema_version,
        result_version=current.version if current else None,
        result_source=current.source if current else None,
        normalized_result=current.normalized_result if current is not None else None,
        overall_confidence=current.overall_confidence if current else None,
        coach_review=coach,
        doctor_review=doctor,
        fully_reviewed=fully_reviewed,
        unverified_warning=current is not None and not fully_reviewed,
        error_code=analysis.error_code,
        safe_error_message=analysis.error_message,
        photo_validation=photo_validation,
        created_at=analysis.created_at,
        completed_at=analysis.completed_at,
    )


@router.get("/{session_id}/analysis", response_model=BodyAnalysisResponse | None)
def get_session_analysis(
    session_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
) -> BodyAnalysisResponse | None:
    try:
        analysis = BodyAnalysisService(db).latest_for_session(session_id, user.id)
    except BodyAnalysisNotFoundError:
        raise _not_found() from None
    return _response(db, analysis) if analysis else None


async def _execute_background(
    service: BodyAnalysisService,
    analysis_id: UUID,
    runtime: BodyAnalysisRuntimeDependency,
) -> None:
    await service.execute(
        analysis_id,
        runtime.provider,
        runtime.storage,
        runtime.config,
    )


@router.post(
    "/{session_id}/analysis",
    response_model=BodyAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_trusted_origin)],
)
def start_session_analysis(
    session_id: UUID,
    background_tasks: BackgroundTasks,
    db: DatabaseSession,
    user: CurrentUser,
    runtime: BodyAnalysisRuntimeDependency,
) -> BodyAnalysisResponse:
    try:
        service = BodyAnalysisService(db)
        analysis = service.queue(session_id, user.id, runtime.config)
    except BodyAnalysisNotFoundError:
        raise _not_found() from None
    except BodyAnalysisStateError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Body photo session is not ready for analysis",
        ) from None
    background_tasks.add_task(_execute_background, service, analysis.id, runtime)
    return _response(db, analysis)


@router.post(
    "/{session_id}/analysis/retry",
    response_model=BodyAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_trusted_origin)],
)
def retry_session_analysis(
    session_id: UUID,
    background_tasks: BackgroundTasks,
    db: DatabaseSession,
    user: CurrentUser,
    runtime: BodyAnalysisRuntimeDependency,
) -> BodyAnalysisResponse:
    service = BodyAnalysisService(db)
    try:
        latest = service.latest_for_session(session_id, user.id)
        if latest is None:
            raise BodyAnalysisNotFoundError
        if latest.status not in {
            BodyAnalysisStatus.FAILED,
            BodyAnalysisStatus.QUEUED,
            BodyAnalysisStatus.VALIDATING,
            BodyAnalysisStatus.ANALYZING,
        }:
            raise BodyAnalysisStateError("only failed or stale analyses can be retried")
        analysis = service.retry(latest.id, user.id, runtime.config)
    except BodyAnalysisNotFoundError:
        raise _not_found() from None
    except BodyAnalysisStateError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    background_tasks.add_task(_execute_background, service, analysis.id, runtime)
    return _response(db, analysis)


@admin_router.post(
    "/{analysis_id}/retry",
    response_model=BodyAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_trusted_origin)],
)
def retry_analysis_as_admin(
    analysis_id: UUID,
    background_tasks: BackgroundTasks,
    db: DatabaseSession,
    _admin: AdminUser,
    runtime: BodyAnalysisRuntimeDependency,
) -> BodyAnalysisResponse:
    analysis = db.scalar(
        select(BodyAnalysis).where(BodyAnalysis.id == analysis_id).join(BodyAnalysis.session)
    )
    if analysis is None:
        raise _not_found()
    try:
        service = BodyAnalysisService(db)
        latest = service.latest_for_session(analysis.session_id, analysis.session.user_id)
        if latest is None or latest.id != analysis.id:
            raise BodyAnalysisStateError("only the latest analysis revision can be retried")
        queued = service.retry(
            analysis.id,
            analysis.session.user_id,
            runtime.config,
        )
    except BodyAnalysisNotFoundError:
        raise _not_found() from None
    except BodyAnalysisStateError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    background_tasks.add_task(_execute_background, BodyAnalysisService(db), queued.id, runtime)
    return _response(db, queued)


@review_router.post(
    "/{analysis_id}/review",
    response_model=SpecialistReviewResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def submit_specialist_review(
    analysis_id: UUID,
    payload: SpecialistReviewRequest,
    db: DatabaseSession,
    admin: AdminUser,
) -> SpecialistReviewResponse:
    try:
        review = BodyAnalysisService(db).review(
            analysis_id,
            admin.id,
            ReviewSubmission.model_validate(payload.model_dump()),
        )
    except BodyAnalysisNotFoundError:
        raise _not_found() from None
    except BodyAnalysisStateError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    return SpecialistReviewResponse(
        id=review.id,
        analysis_id=review.analysis_id,
        result_version_id=review.result_version_id,
        reviewer_id=review.reviewer_id,
        role=review.reviewer_role,
        decision=review.decision,
        notes=review.notes,
        reviewed_at=review.created_at,
    )


@review_router.get("/{analysis_id}", response_model=BodyAnalysisReviewDetail)
def get_specialist_review_detail(
    analysis_id: UUID,
    db: DatabaseSession,
    _admin: AdminUser,
) -> BodyAnalysisReviewDetail:
    analysis = db.get(BodyAnalysis, analysis_id)
    if analysis is None:
        raise _not_found()
    versions = list(
        db.scalars(
            select(BodyAnalysisResultVersion)
            .where(BodyAnalysisResultVersion.analysis_id == analysis.id)
            .order_by(BodyAnalysisResultVersion.version)
        ).all()
    )
    version_numbers = {version.id: version.version for version in versions}
    reviews = list(
        db.scalars(
            select(BodyAnalysisReview)
            .where(BodyAnalysisReview.analysis_id == analysis.id)
            .order_by(BodyAnalysisReview.created_at, BodyAnalysisReview.id)
        ).all()
    )
    return BodyAnalysisReviewDetail(
        analysis=_response(db, analysis),
        result_versions=[
            BodyAnalysisResultVersionResponse(
                id=version.id,
                version=version.version,
                source=version.source,
                normalized_result=version.normalized_result,
                overall_confidence=version.overall_confidence,
                created_by_user_id=version.created_by_user_id,
                created_at=version.created_at,
            )
            for version in versions
        ],
        reviews=[
            BodyAnalysisReviewHistoryResponse(
                id=review.id,
                analysis_id=review.analysis_id,
                result_version_id=review.result_version_id,
                result_version=version_numbers[review.result_version_id],
                reviewer_id=review.reviewer_id,
                role=review.reviewer_role,
                decision=review.decision,
                notes=review.notes,
                reviewed_at=review.created_at,
            )
            for review in reviews
        ],
    )
