from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import BinaryIO, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.body_analysis.enums import (
    BodyAnalysisResultSource,
    BodyAnalysisReviewDecision,
    BodyAnalysisReviewerRole,
    BodyAnalysisStatus,
)
from app.body_analysis.models import BodyAnalysis, BodyAnalysisResultVersion, BodyAnalysisReview
from app.body_analysis.normalization import MedicalClaimError, normalize_body_analysis
from app.body_analysis.providers import (
    AIProvider,
    AIProviderError,
    ImageInput,
    ModelRoute,
    ProviderErrorCode,
    StructuredGenerationRequest,
)
from app.body_analysis.schemas import NormalizedBodyAnalysis
from app.body_photos.enums import BodyPhotoSessionState, BodyPhotoView
from app.body_photos.models import BodyPhoto, BodyPhotoSession


class BodyAnalysisNotFoundError(LookupError):
    pass


class BodyAnalysisStateError(ValueError):
    pass


class BodyAnalysisInputError(ValueError):
    pass


class BodyAnalysisReadStorage(Protocol):
    def open(self, key: str) -> BinaryIO: ...


class AnalysisExecutionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_name: str = Field(min_length=1, max_length=50)
    primary_model: str = Field(min_length=1, max_length=300)
    fallback_models: tuple[str, ...] = Field(default=(), max_length=5)
    prompt_version: str = Field(min_length=1, max_length=64)
    schema_version: str = Field(pattern=r"^[0-9]+\.[0-9]+$", max_length=16)
    temperature: float = Field(default=0.0, ge=0, le=1)
    max_output_tokens: int = Field(default=4096, ge=1, le=65_536)


class ReviewSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: BodyAnalysisReviewerRole
    decision: BodyAnalysisReviewDecision
    notes: str | None = Field(default=None, min_length=1, max_length=2000)
    corrected_result: dict[str, object] | None = None


@dataclass(frozen=True)
class EffectiveBodyAnalysisResult:
    analysis_id: UUID
    result_version_id: UUID
    version: int
    normalized_result: NormalizedBodyAnalysis
    source: BodyAnalysisResultSource
    coach_approved: bool
    doctor_approved: bool

    @property
    def fully_reviewed(self) -> bool:
        return self.coach_approved and self.doctor_approved

    @property
    def provenance(self) -> str:
        if self.fully_reviewed:
            return "fully_reviewed"
        if self.coach_approved:
            return "coach_reviewed"
        if self.doctor_approved:
            return "doctor_reviewed"
        return "ai_only"


_ANALYSIS_PROMPT = """You analyze only visible muscular development, proportions, and visible
asymmetry using the three processed head-cropped body views. Do not diagnose disease, injury,
deformity, posture disorders, or medical conditions. Do not infer identity, ethnicity,
personality, or actual muscular strength. Account for lighting, pose, body fat, clothing,
perspective, and visibility. Use 'visibly developed', 'relatively lagging', or 'uncertain'.
Do not invent findings. Return lower confidence and uncertain when evidence is insufficient.
The result is provisional and requires coach and doctor review. Return only the requested JSON.
"""


class BodyAnalysisService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def queue(
        self,
        session_id: UUID,
        user_id: UUID,
        config: AnalysisExecutionConfig,
    ) -> BodyAnalysis:
        photo_session = self._owner_photo_session(session_id, user_id, lock=True)
        if photo_session.state not in {
            BodyPhotoSessionState.QUEUED,
            BodyPhotoSessionState.VALIDATING,
            BodyPhotoSessionState.ANALYZING,
            BodyPhotoSessionState.REVIEW_PENDING,
            BodyPhotoSessionState.COMPLETED,
            BodyPhotoSessionState.FAILED,
        }:
            raise BodyAnalysisStateError("body photo session has not been submitted")
        latest = self._latest_analysis(session_id)
        if latest is not None and latest.status is not BodyAnalysisStatus.FAILED:
            return latest
        return self._create_analysis(photo_session, config, replaces=latest)

    def retry(
        self,
        analysis_id: UUID,
        user_id: UUID,
        config: AnalysisExecutionConfig,
    ) -> BodyAnalysis:
        previous = self.get_analysis(analysis_id, user_id)
        photo_session = self._owner_photo_session(previous.session_id, user_id, lock=True)
        latest = self._latest_analysis(photo_session.id)
        if latest is not None and latest.status in {
            BodyAnalysisStatus.QUEUED,
            BodyAnalysisStatus.VALIDATING,
            BodyAnalysisStatus.ANALYZING,
        }:
            return latest
        return self._create_analysis(photo_session, config, replaces=previous)

    def _create_analysis(
        self,
        photo_session: BodyPhotoSession,
        config: AnalysisExecutionConfig,
        *,
        replaces: BodyAnalysis | None,
    ) -> BodyAnalysis:
        revision = (
            int(
                self._db.scalar(
                    select(func.coalesce(func.max(BodyAnalysis.revision), 0)).where(
                        BodyAnalysis.session_id == photo_session.id
                    )
                )
                or 0
            )
            + 1
        )
        analysis = BodyAnalysis(
            session_id=photo_session.id,
            replaces_analysis_id=replaces.id if replaces else None,
            revision=revision,
            provider=config.provider_name,
            model_id=config.primary_model,
            fallback_model_id=(config.fallback_models[0] if config.fallback_models else None),
            prompt_version=config.prompt_version,
            schema_version=config.schema_version,
            status=BodyAnalysisStatus.QUEUED,
        )
        self._db.add(analysis)
        try:
            self._db.commit()
            self._db.refresh(analysis)
        except SQLAlchemyError:
            self._db.rollback()
            raise
        return analysis

    async def execute(
        self,
        analysis_id: UUID,
        provider: AIProvider,
        storage: BodyAnalysisReadStorage,
        config: AnalysisExecutionConfig | None = None,
    ) -> BodyAnalysis:
        analysis = self._analysis(analysis_id, lock=True)
        if analysis.status is not BodyAnalysisStatus.QUEUED:
            return analysis
        execution_config = config or AnalysisExecutionConfig(
            provider_name=analysis.provider,
            primary_model=analysis.model_id,
            fallback_models=(analysis.fallback_model_id,) if analysis.fallback_model_id else (),
            prompt_version=analysis.prompt_version,
            schema_version=analysis.schema_version,
        )
        try:
            images = self._prepare_images(analysis)
            analysis.status = BodyAnalysisStatus.ANALYZING
            analysis.attempt_count += 1
            analysis.started_at = datetime.now(UTC)
            analysis.session.state = BodyPhotoSessionState.ANALYZING
            self._db.commit()

            response = await provider.analyze_images(
                self._request(execution_config),
                images=tuple(
                    ImageInput(
                        label=photo.view.value,
                        mime_type=photo.mime_type,
                        base64_data=base64.b64encode(
                            self._read(storage, photo.storage_key)
                        ).decode(),
                    )
                    for photo in images
                ),
            )
            normalized = normalize_body_analysis(response.payload)
            analysis.raw_result = response.payload
            analysis.normalized_result = normalized.model_dump(mode="json")
            analysis.overall_confidence = normalized.overall_confidence
            analysis.model_id = response.model_id
            analysis.provider_request_id = response.provider_request_id
            analysis.input_tokens = response.input_tokens
            analysis.output_tokens = response.output_tokens
            analysis.request_cost = response.cost
            analysis.error_code = None
            analysis.error_message = None
            analysis.status = BodyAnalysisStatus.REVIEW_PENDING
            analysis.completed_at = datetime.now(UTC)
            analysis.session.state = BodyPhotoSessionState.REVIEW_PENDING
            self._db.add(
                BodyAnalysisResultVersion(
                    analysis_id=analysis.id,
                    version=1,
                    source=BodyAnalysisResultSource.AI,
                    normalized_result=normalized.model_dump(mode="json"),
                    overall_confidence=normalized.overall_confidence,
                )
            )
            self._db.commit()
        except Exception as error:
            self._db.rollback()
            analysis = self._analysis(analysis_id, lock=True)
            provider_error = self._safe_provider_error(provider, error)
            analysis.status = BodyAnalysisStatus.FAILED
            analysis.error_code = provider_error.code.value
            analysis.error_message = "Body analysis could not be completed. Please retry later."
            analysis.provider_request_id = provider_error.provider_request_id
            analysis.completed_at = datetime.now(UTC)
            analysis.session.state = self._session_state_after_failure(analysis)
            self._db.commit()
        return self._analysis(analysis_id)

    def get_analysis(self, analysis_id: UUID, user_id: UUID) -> BodyAnalysis:
        analysis = self._db.scalar(
            select(BodyAnalysis)
            .join(BodyPhotoSession)
            .where(BodyAnalysis.id == analysis_id, BodyPhotoSession.user_id == user_id)
            .options(selectinload(BodyAnalysis.session))
        )
        if analysis is None:
            raise BodyAnalysisNotFoundError
        return analysis

    def latest_for_session(self, session_id: UUID, user_id: UUID) -> BodyAnalysis | None:
        self._owner_photo_session(session_id, user_id)
        return self._latest_analysis(session_id)

    def effective_result(self, session_id: UUID, user_id: UUID) -> EffectiveBodyAnalysisResult:
        self._owner_photo_session(session_id, user_id)
        analyses = self._db.scalars(
            select(BodyAnalysis)
            .where(
                BodyAnalysis.session_id == session_id,
                BodyAnalysis.status.in_(
                    [BodyAnalysisStatus.REVIEW_PENDING, BodyAnalysisStatus.COMPLETED]
                ),
            )
            .order_by(BodyAnalysis.revision.desc())
        ).all()
        for analysis in analyses:
            version = self._current_version(analysis.id)
            if version is not None:
                coach, doctor = self._approval_state(analysis.id, version.id)
                return EffectiveBodyAnalysisResult(
                    analysis_id=analysis.id,
                    result_version_id=version.id,
                    version=version.version,
                    normalized_result=NormalizedBodyAnalysis.model_validate(
                        version.normalized_result
                    ),
                    source=version.source,
                    coach_approved=coach,
                    doctor_approved=doctor,
                )
        raise BodyAnalysisNotFoundError

    def review(
        self,
        analysis_id: UUID,
        reviewer_id: UUID,
        submission: ReviewSubmission,
    ) -> BodyAnalysisReview:
        analysis = self._analysis(analysis_id, lock=True)
        if analysis.status not in {
            BodyAnalysisStatus.REVIEW_PENDING,
            BodyAnalysisStatus.COMPLETED,
        }:
            raise BodyAnalysisStateError("analysis is not ready for specialist review")
        current = self._current_version(analysis.id)
        if current is None:
            raise BodyAnalysisStateError("analysis has no normalized result")
        if submission.corrected_result is not None:
            corrected = normalize_body_analysis(submission.corrected_result)
            replacement = BodyAnalysisResultVersion(
                analysis_id=analysis.id,
                replaces_version_id=current.id,
                version=current.version + 1,
                source=BodyAnalysisResultSource(submission.role.value),
                normalized_result=corrected.model_dump(mode="json"),
                overall_confidence=corrected.overall_confidence,
                created_by_user_id=reviewer_id,
            )
            self._db.add(replacement)
            self._db.flush()
            current = replacement
            analysis.normalized_result = corrected.model_dump(mode="json")
            analysis.overall_confidence = corrected.overall_confidence
        review = BodyAnalysisReview(
            analysis_id=analysis.id,
            result_version_id=current.id,
            reviewer_id=reviewer_id,
            reviewer_role=submission.role,
            decision=submission.decision,
            notes=submission.notes,
        )
        self._db.add(review)
        self._db.flush()
        coach, doctor = self._approval_state(analysis.id, current.id)
        if coach and doctor:
            analysis.status = BodyAnalysisStatus.COMPLETED
            analysis.session.state = BodyPhotoSessionState.COMPLETED
        else:
            analysis.status = BodyAnalysisStatus.REVIEW_PENDING
            analysis.session.state = BodyPhotoSessionState.REVIEW_PENDING
        try:
            self._db.commit()
            self._db.refresh(review)
        except SQLAlchemyError:
            self._db.rollback()
            raise
        return review

    def _owner_photo_session(
        self, session_id: UUID, user_id: UUID, *, lock: bool = False
    ) -> BodyPhotoSession:
        statement = select(BodyPhotoSession).where(
            BodyPhotoSession.id == session_id,
            BodyPhotoSession.user_id == user_id,
            BodyPhotoSession.state != BodyPhotoSessionState.DELETED,
        )
        if lock:
            statement = statement.with_for_update()
        photo_session = self._db.scalar(statement)
        if photo_session is None:
            raise BodyAnalysisNotFoundError
        return photo_session

    def _analysis(self, analysis_id: UUID, *, lock: bool = False) -> BodyAnalysis:
        statement = (
            select(BodyAnalysis)
            .where(BodyAnalysis.id == analysis_id)
            .options(selectinload(BodyAnalysis.session))
        )
        if lock:
            statement = statement.with_for_update()
        analysis = self._db.scalar(statement)
        if analysis is None:
            raise BodyAnalysisNotFoundError
        return analysis

    def _latest_analysis(self, session_id: UUID) -> BodyAnalysis | None:
        return self._db.scalar(
            select(BodyAnalysis)
            .where(BodyAnalysis.session_id == session_id)
            .order_by(BodyAnalysis.revision.desc())
            .limit(1)
        )

    def _prepare_images(self, analysis: BodyAnalysis) -> tuple[BodyPhoto, ...]:
        photos = tuple(
            self._db.scalars(
                select(BodyPhoto)
                .where(BodyPhoto.session_id == analysis.session_id)
                .order_by(BodyPhoto.view)
            ).all()
        )
        if {photo.view for photo in photos} != set(BodyPhotoView) or any(
            not photo.client_crop_confirmed or not photo.server_geometry_checked for photo in photos
        ):
            raise BodyAnalysisInputError("three validated processed views are required")
        return photos

    @staticmethod
    def _read(storage: BodyAnalysisReadStorage, key: str) -> bytes:
        with storage.open(key) as handle:
            return handle.read()

    @staticmethod
    def _request(config: AnalysisExecutionConfig) -> StructuredGenerationRequest:
        return StructuredGenerationRequest(
            system_prompt=_ANALYSIS_PROMPT,
            input_payload={
                "task": "analyze_processed_body_views",
                "schema_version": config.schema_version,
            },
            response_schema=NormalizedBodyAnalysis.model_json_schema(),
            schema_name="fitsho_body_analysis",
            route=ModelRoute(
                primary_model=config.primary_model,
                fallback_models=config.fallback_models,
            ),
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
        )

    @staticmethod
    def _safe_provider_error(provider: AIProvider, error: Exception) -> AIProviderError:
        if isinstance(error, (ValidationError, MedicalClaimError, BodyAnalysisInputError)):
            return AIProviderError(
                ProviderErrorCode.INVALID_OUTPUT,
                "The provider response did not match the body-analysis contract.",
            )
        return provider.normalize_error(error)

    def _current_version(self, analysis_id: UUID) -> BodyAnalysisResultVersion | None:
        return self._db.scalar(
            select(BodyAnalysisResultVersion)
            .where(BodyAnalysisResultVersion.analysis_id == analysis_id)
            .order_by(BodyAnalysisResultVersion.version.desc())
            .limit(1)
        )

    def _session_state_after_failure(self, failed_analysis: BodyAnalysis) -> BodyPhotoSessionState:
        prior = self._db.scalar(
            select(BodyAnalysis)
            .where(
                BodyAnalysis.session_id == failed_analysis.session_id,
                BodyAnalysis.id != failed_analysis.id,
                BodyAnalysis.status.in_(
                    [BodyAnalysisStatus.REVIEW_PENDING, BodyAnalysisStatus.COMPLETED]
                ),
            )
            .order_by(BodyAnalysis.revision.desc())
            .limit(1)
        )
        if prior is None:
            return BodyPhotoSessionState.FAILED
        if prior.status is BodyAnalysisStatus.COMPLETED:
            return BodyPhotoSessionState.COMPLETED
        return BodyPhotoSessionState.REVIEW_PENDING

    def _approval_state(self, analysis_id: UUID, version_id: UUID) -> tuple[bool, bool]:
        reviews = self._db.scalars(
            select(BodyAnalysisReview)
            .where(
                BodyAnalysisReview.analysis_id == analysis_id,
                BodyAnalysisReview.result_version_id == version_id,
            )
            .order_by(BodyAnalysisReview.created_at, BodyAnalysisReview.id)
        ).all()
        latest = {review.reviewer_role: review.decision for review in reviews}
        return (
            latest.get(BodyAnalysisReviewerRole.COACH) is BodyAnalysisReviewDecision.APPROVED,
            latest.get(BodyAnalysisReviewerRole.DOCTOR) is BodyAnalysisReviewDecision.APPROVED,
        )
