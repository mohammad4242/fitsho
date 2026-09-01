from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.body_analysis.api_schemas import (
    BodyAnalysisExperienceV4,
    BodyAnalysisInputSnapshotResponse,
    BodyAnalysisResponse,
    SpecialistReviewState,
)
from app.body_analysis.comparison_models import BodyProgressComparison
from app.body_analysis.comparison_schemas import BodyProgressComparisonResponse
from app.body_analysis.enums import (
    BodyAnalysisReviewDecision,
    BodyAnalysisReviewerRole,
)
from app.body_analysis.history_schemas import (
    BodyProgressTimelineComparison,
    BodyProgressTimelineItem,
    BodyProgressTimelineResponse,
    BodyProgressTimelineReviewState,
    BodyProgressTimelineSession,
)
from app.body_analysis.models import BodyAnalysis, BodyAnalysisResultVersion, BodyAnalysisReview
from app.body_analysis.normalization import normalize_visual_physique_assessment_v4
from app.body_analysis.presentation import build_body_analysis_experience_v4
from app.body_analysis.schemas import BodyPhotoPreflight, NormalizedBodyAnalysis
from app.body_photos.enums import BodyPhotoSessionState
from app.body_photos.models import BodyPhotoSession
from app.body_photos.schemas import BodyPhotoResponse


class BodyProgressHistoryService:
    """Read the owner-scoped body-progress timeline in bounded bulk queries."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def timeline(self, user_id: UUID) -> BodyProgressTimelineResponse:
        sessions = list(
            self._db.scalars(
                select(BodyPhotoSession)
                .where(
                    BodyPhotoSession.user_id == user_id,
                    BodyPhotoSession.state != BodyPhotoSessionState.DELETED,
                )
                .options(selectinload(BodyPhotoSession.photos))
                .order_by(BodyPhotoSession.created_at.desc(), BodyPhotoSession.id.desc())
            ).all()
        )
        if not sessions:
            return BodyProgressTimelineResponse(items=[])

        session_ids = tuple(session.id for session in sessions)
        analyses = list(
            self._db.scalars(
                select(BodyAnalysis)
                .where(BodyAnalysis.session_id.in_(session_ids))
                .order_by(BodyAnalysis.revision.desc(), BodyAnalysis.id.desc())
            ).all()
        )
        latest_analysis_by_session: dict[UUID, BodyAnalysis] = {}
        for analysis in analyses:
            latest_analysis_by_session.setdefault(analysis.session_id, analysis)

        analysis_ids = tuple(analysis.id for analysis in latest_analysis_by_session.values())
        versions_by_analysis: dict[UUID, BodyAnalysisResultVersion] = {}
        if analysis_ids:
            versions = self._db.scalars(
                select(BodyAnalysisResultVersion)
                .where(BodyAnalysisResultVersion.analysis_id.in_(analysis_ids))
                .order_by(
                    BodyAnalysisResultVersion.version.desc(),
                    BodyAnalysisResultVersion.id.desc(),
                )
            ).all()
            for version in versions:
                versions_by_analysis.setdefault(version.analysis_id, version)

        current_version_ids = tuple(version.id for version in versions_by_analysis.values())
        reviews_by_version: dict[UUID, dict[BodyAnalysisReviewerRole, BodyAnalysisReview]] = {}
        if current_version_ids:
            reviews = self._db.scalars(
                select(BodyAnalysisReview)
                .where(BodyAnalysisReview.result_version_id.in_(current_version_ids))
                .order_by(BodyAnalysisReview.created_at, BodyAnalysisReview.id)
            ).all()
            for review in reviews:
                reviews_by_version.setdefault(review.result_version_id, {})[
                    review.reviewer_role
                ] = review

        comparisons_by_version: dict[UUID, BodyProgressComparison] = {}
        comparisons = self._db.scalars(
            select(BodyProgressComparison)
            .where(
                BodyProgressComparison.user_id == user_id,
                BodyProgressComparison.current_session_id.in_(session_ids),
            )
            .order_by(BodyProgressComparison.comparison_version.desc())
        ).all()
        for comparison in comparisons:
            comparisons_by_version.setdefault(comparison.current_result_version_id, comparison)

        session_by_id = {session.id: session for session in sessions}
        items = [
            self._item(
                session,
                latest_analysis_by_session.get(session.id),
                versions_by_analysis,
                reviews_by_version,
                comparisons_by_version,
                session_by_id,
            )
            for session in sessions
        ]
        return BodyProgressTimelineResponse(items=items)

    def _item(
        self,
        session: BodyPhotoSession,
        analysis: BodyAnalysis | None,
        versions_by_analysis: dict[UUID, BodyAnalysisResultVersion],
        reviews_by_version: dict[UUID, dict[BodyAnalysisReviewerRole, BodyAnalysisReview]],
        comparisons_by_version: dict[UUID, BodyProgressComparison],
        session_by_id: dict[UUID, BodyPhotoSession],
    ) -> BodyProgressTimelineItem:
        version = versions_by_analysis.get(analysis.id) if analysis is not None else None
        reviews = reviews_by_version.get(version.id, {}) if version is not None else {}
        review_state = self._review_state(version, reviews)
        stored_comparison = (
            comparisons_by_version.get(version.id) if version is not None else None
        )
        return BodyProgressTimelineItem(
            session=BodyProgressTimelineSession(
                id=session.id,
                cycle_id=session.cycle_id,
                purpose=session.purpose,
                state=session.state,
                submitted_at=session.submitted_at,
                created_at=session.created_at,
                updated_at=session.updated_at,
            ),
            photos=self._photos(session),
            analysis=(
                self._analysis_response(analysis, version, reviews)
                if analysis is not None
                else None
            ),
            snapshot=self._snapshot_response(analysis),
            comparison=(
                self._comparison_response(
                    stored_comparison,
                    session_by_id,
                )
                if stored_comparison is not None
                else None
            ),
            review_state=review_state,
        )

    @staticmethod
    def _photos(session: BodyPhotoSession) -> tuple[BodyPhotoResponse, ...]:
        return tuple(
            BodyPhotoResponse(
                id=photo.id,
                view=photo.view,
                mime_type=photo.mime_type,
                byte_size=photo.byte_size,
                width=photo.width,
                height=photo.height,
                content_url=(
                    f"/api/v1/body-photo-sessions/{session.id}/photos/"
                    f"{photo.view.value}/content"
                ),
                created_at=photo.created_at,
                updated_at=photo.updated_at,
            )
            for photo in sorted(session.photos, key=lambda item: item.view.value)
        )

    @staticmethod
    def _review_state(
        version: BodyAnalysisResultVersion | None,
        reviews: dict[BodyAnalysisReviewerRole, BodyAnalysisReview],
    ) -> BodyProgressTimelineReviewState:
        def state(role: BodyAnalysisReviewerRole) -> SpecialistReviewState:
            review = reviews.get(role)
            return SpecialistReviewState(
                role=role,
                decision=review.decision if review is not None else None,
                reviewed_at=review.created_at if review is not None else None,
                reviewed_result_version=version.version if review is not None and version else None,
            )

        coach = state(BodyAnalysisReviewerRole.COACH)
        doctor = state(BodyAnalysisReviewerRole.DOCTOR)
        return BodyProgressTimelineReviewState(
            coach=coach,
            doctor=doctor,
            fully_reviewed=(
                coach.decision is BodyAnalysisReviewDecision.APPROVED
                and doctor.decision is BodyAnalysisReviewDecision.APPROVED
            ),
        )

    def _analysis_response(
        self,
        analysis: BodyAnalysis,
        version: BodyAnalysisResultVersion | None,
        reviews: dict[BodyAnalysisReviewerRole, BodyAnalysisReview],
    ) -> BodyAnalysisResponse:
        review_state = self._review_state(version, reviews)
        photo_validation = None
        if isinstance(analysis.raw_result, dict):
            raw_validation = analysis.raw_result.get("photo_validation")
            if isinstance(raw_validation, dict):
                try:
                    photo_validation = BodyPhotoPreflight.model_validate(raw_validation)
                except (TypeError, ValueError):
                    photo_validation = None
        experience_result = self._experience_result(analysis, version, review_state)
        return BodyAnalysisResponse(
            id=analysis.id,
            cycle_id=analysis.cycle_id,
            session_id=analysis.session_id,
            revision=analysis.revision,
            status=analysis.status,
            provider=analysis.provider,
            model_id=analysis.model_id,
            schema_version=analysis.schema_version,
            result_version=version.version if version is not None else None,
            result_source=version.source if version is not None else None,
            normalized_result=version.normalized_result if version is not None else None,
            visual_result=version.visual_result if version is not None else None,
            experience_result=experience_result,
            overall_confidence=version.overall_confidence if version is not None else None,
            coach_review=review_state.coach,
            doctor_review=review_state.doctor,
            fully_reviewed=review_state.fully_reviewed,
            unverified_warning=version is not None and not review_state.fully_reviewed,
            error_code=analysis.error_code,
            safe_error_message=analysis.error_message,
            photo_validation=photo_validation,
            created_at=analysis.created_at,
            completed_at=analysis.completed_at,
        )

    @staticmethod
    def _snapshot_response(
        analysis: BodyAnalysis | None,
    ) -> BodyAnalysisInputSnapshotResponse | None:
        if analysis is None or analysis.schema_version != "4.0":
            return None
        raw_result = analysis.raw_result
        raw_snapshot = raw_result.get("input_snapshot") if isinstance(raw_result, dict) else None
        if not isinstance(raw_snapshot, dict):
            return None
        try:
            from app.body_analysis.service import BodyAnalysisInputSnapshot

            snapshot = BodyAnalysisInputSnapshot.model_validate(raw_snapshot)
            return BodyAnalysisInputSnapshotResponse.model_validate(
                snapshot.model_dump(mode="json", exclude={"photo_versions"})
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _experience_result(
        analysis: BodyAnalysis,
        version: BodyAnalysisResultVersion | None,
        review_state: BodyProgressTimelineReviewState,
    ) -> BodyAnalysisExperienceV4 | None:
        if analysis.schema_version != "4.0" or version is None:
            return None
        raw_result = analysis.raw_result
        raw_analysis = raw_result.get("analysis") if isinstance(raw_result, dict) else None
        if not isinstance(raw_analysis, dict):
            return None
        try:
            from app.body_analysis.service import BodyAnalysisInputSnapshot

            raw_snapshot = (
                raw_result.get("input_snapshot") if isinstance(raw_result, dict) else None
            )
            snapshot = BodyAnalysisInputSnapshot.model_validate(raw_snapshot)
            evidence = normalize_visual_physique_assessment_v4(raw_analysis)
            normalized = NormalizedBodyAnalysis.model_validate(version.normalized_result)
            return build_body_analysis_experience_v4(
                normalized_result=normalized,
                evidence=evidence,
                snapshot=snapshot,
                coach_approved=review_state.coach.decision
                is BodyAnalysisReviewDecision.APPROVED,
                doctor_approved=review_state.doctor.decision
                is BodyAnalysisReviewDecision.APPROVED,
            )
        except (TypeError, ValueError):
            return None

    def _comparison_response(
        self,
        comparison: BodyProgressComparison,
        session_by_id: dict[UUID, BodyPhotoSession],
    ) -> BodyProgressTimelineComparison | None:
        previous_session = session_by_id.get(comparison.previous_session_id)
        current_session = session_by_id.get(comparison.current_session_id)
        if previous_session is None or current_session is None:
            return None
        normalized = BodyProgressComparisonResponse(
            id=comparison.id,
            previous_session_id=comparison.previous_session_id,
            current_session_id=comparison.current_session_id,
            previous_result_version_id=comparison.previous_result_version_id,
            current_result_version_id=comparison.current_result_version_id,
            comparison_version=comparison.comparison_version,
            schema_version=comparison.schema_version,
            normalized_result=comparison.normalized_result,
            quality_snapshot=comparison.quality_snapshot,
            context_snapshot=comparison.context_snapshot,
            created_at=comparison.created_at,
        )
        return BodyProgressTimelineComparison(
            **normalized.model_dump(mode="python"),
            previous_session_date=previous_session.created_at,
            current_session_date=current_session.created_at,
            interval_days=(
                current_session.created_at.date() - previous_session.created_at.date()
            ).days,
            before_photos=self._photos(previous_session),
            after_photos=self._photos(current_session),
        )
