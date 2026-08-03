from __future__ import annotations

import asyncio
import io
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.body_analysis.enums import (
    BodyAnalysisReviewDecision,
    BodyAnalysisReviewerRole,
    BodyAnalysisStatus,
)
from app.body_analysis.models import BodyAnalysis, BodyAnalysisResultVersion, BodyAnalysisReview
from app.body_analysis.providers import (
    AIProviderError,
    ProviderErrorCode,
    StructuredGenerationResponse,
)
from app.body_analysis.service import (
    AnalysisExecutionConfig,
    BodyAnalysisService,
    ReviewSubmission,
)
from app.body_photos.enums import BodyPhotoPurpose, BodyPhotoSessionState, BodyPhotoView
from app.body_photos.models import BodyPhoto, BodyPhotoSession


def _normalized_payload(*, classification: str = "clear_lag") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "overall_confidence": 0.86,
        "findings": [
            {
                "body_area": "shoulders",
                "classification": classification,
                "severity": 0.72 if classification != "uncertain" else None,
                "confidence": 0.88,
                "supporting_views": ["front", "back"],
                "explanation": "Shoulders appear visibly less developed relative to the torso.",
                "limitations": [],
                "suggested_training_emphasis": (
                    ["lateral_deltoid", "rear_deltoid"] if classification != "uncertain" else []
                ),
                "medical_review_recommended": False,
            }
        ],
        "summary": {
            "visible_strengths": [],
            "priority_areas": ["shoulders"] if classification == "clear_lag" else [],
            "moderate_attention_areas": [],
            "uncertain_areas": ["shoulders"] if classification == "uncertain" else [],
        },
        "requires_coach_review": True,
        "requires_doctor_review": True,
    }


class _Storage:
    def open(self, key: str) -> io.BytesIO:
        return io.BytesIO(f"processed-{key}".encode())


class _Provider:
    def __init__(self, payload: dict[str, object] | None = None) -> None:
        self.payload = payload or _normalized_payload()
        self.calls = 0

    async def analyze_images(self, request: object, *, images: tuple[object, ...]) -> object:
        self.calls += 1
        assert len(images) == 3
        return StructuredGenerationResponse(
            payload=self.payload,
            model_id="vision-primary",
            attempted_models=("vision-primary",),
            provider_request_id="req-safe-id",
            input_tokens=100,
            output_tokens=200,
            cost=Decimal("0.012"),
        )

    def normalize_error(self, error: Exception) -> AIProviderError:
        if isinstance(error, AIProviderError):
            return error
        return AIProviderError(ProviderErrorCode.PROVIDER_UNAVAILABLE, "Provider unavailable")


class _FailingProvider(_Provider):
    async def analyze_images(self, request: object, *, images: tuple[object, ...]) -> object:
        self.calls += 1
        raise AIProviderError(
            ProviderErrorCode.UNAUTHORIZED,
            "The AI provider credential was rejected.",
        )


def _submitted_session(db: Session, user: User | None = None) -> tuple[User, BodyPhotoSession]:
    user = user or User(
        id=uuid4(), email=f"analysis-{uuid4()}@example.com", password_hash="not-used"
    )
    session = BodyPhotoSession(
        user_id=user.id,
        purpose=BodyPhotoPurpose.PROGRESS_CHECK,
        state=BodyPhotoSessionState.QUEUED,
    )
    db.add_all([user, session])
    db.flush()
    for view in BodyPhotoView:
        db.add(
            BodyPhoto(
                session_id=session.id,
                view=view,
                storage_key=f"aa/{uuid4().hex}.jpg",
                mime_type="image/jpeg",
                byte_size=1024,
                width=600,
                height=1200,
                client_crop_confidence=0.95,
                client_crop_confirmed=True,
                server_geometry_checked=True,
                crop_original_height=1400,
                crop_top=200,
                crop_bottom=1400,
                processed_sha256="a" * 64,
                crop_evidence_sha256="b" * 64,
            )
        )
    db.commit()
    return user, session
def _config() -> AnalysisExecutionConfig:
    return AnalysisExecutionConfig(
        provider_name="openrouter",
        primary_model="vision-primary",
        fallback_models=("vision-fallback",),
        prompt_version="body-v1",
        schema_version="1.0",
        max_output_tokens=3000,
    )


def test_queue_is_idempotent_for_same_session(db: Session) -> None:
    user, session = _submitted_session(db)
    service = BodyAnalysisService(db)

    first = service.queue(session.id, user.id, _config())
    second = service.queue(session.id, user.id, _config())

    assert second.id == first.id
    assert db.scalars(select(BodyAnalysis).where(BodyAnalysis.session_id == session.id)).all() == [
        first
    ]


def test_execution_persists_validated_result_and_is_idempotent(db: Session) -> None:
    user, session = _submitted_session(db)
    provider = _Provider()
    service = BodyAnalysisService(db)
    analysis = service.queue(session.id, user.id, _config())

    completed = asyncio.run(service.execute(analysis.id, provider, _Storage()))
    repeated = asyncio.run(service.execute(analysis.id, provider, _Storage()))

    assert completed.status is BodyAnalysisStatus.REVIEW_PENDING
    assert repeated.id == completed.id
    assert provider.calls == 1
    assert completed.model_id == "vision-primary"
    assert completed.error_message is None
    versions = db.scalars(
        select(BodyAnalysisResultVersion).where(
            BodyAnalysisResultVersion.analysis_id == analysis.id
        )
    ).all()
    assert len(versions) == 1
    assert versions[0].version == 1
    assert versions[0].normalized_result["summary"]["priority_areas"] == ["shoulders"]


def test_execution_sanitizes_provider_failure_and_retry_preserves_prior_success(
    db: Session,
) -> None:
    user, session = _submitted_session(db)
    service = BodyAnalysisService(db)
    successful = service.queue(session.id, user.id, _config())
    asyncio.run(service.execute(successful.id, _Provider(), _Storage()))

    retry = service.retry(successful.id, user.id, _config())
    failed = asyncio.run(service.execute(retry.id, _FailingProvider(), _Storage()))

    assert retry.id != successful.id
    assert failed.status is BodyAnalysisStatus.FAILED
    assert failed.error_code == "unauthorized"
    assert failed.error_message == "Body analysis could not be completed. Please retry later."
    assert "credential" not in failed.error_message.lower()
    assert service.effective_result(session.id, user.id).analysis_id == successful.id
    db.refresh(session)
    assert session.state is BodyPhotoSessionState.REVIEW_PENDING


def test_coach_and_doctor_approvals_are_independent_and_version_bound(db: Session) -> None:
    user, session = _submitted_session(db)
    service = BodyAnalysisService(db)
    analysis = service.queue(session.id, user.id, _config())
    asyncio.run(service.execute(analysis.id, _Provider(), _Storage()))
    coach = User(email=f"coach-{uuid4()}@example.com", password_hash="x", is_admin=True)
    doctor = User(email=f"doctor-{uuid4()}@example.com", password_hash="x", is_admin=True)
    db.add_all([coach, doctor])
    db.commit()

    coach_review = service.review(
        analysis.id,
        coach.id,
        ReviewSubmission(
            role=BodyAnalysisReviewerRole.COACH,
            decision=BodyAnalysisReviewDecision.APPROVED,
            notes="Training emphasis is appropriate.",
        ),
    )
    pending_status = service.get_analysis(analysis.id, user.id).status
    doctor_review = service.review(
        analysis.id,
        doctor.id,
        ReviewSubmission(
            role=BodyAnalysisReviewerRole.DOCTOR,
            decision=BodyAnalysisReviewDecision.APPROVED,
            notes="No diagnostic conclusion is being made.",
        ),
    )

    assert coach_review.reviewer_role is BodyAnalysisReviewerRole.COACH
    assert doctor_review.reviewer_role is BodyAnalysisReviewerRole.DOCTOR
    assert pending_status is BodyAnalysisStatus.REVIEW_PENDING
    assert service.get_analysis(analysis.id, user.id).status is BodyAnalysisStatus.COMPLETED


def test_specialist_correction_creates_history_and_invalidates_old_approval(
    db: Session,
) -> None:
    user, session = _submitted_session(db)
    service = BodyAnalysisService(db)
    analysis = service.queue(session.id, user.id, _config())
    asyncio.run(service.execute(analysis.id, _Provider(), _Storage()))
    coach = User(email=f"coach-{uuid4()}@example.com", password_hash="x", is_admin=True)
    doctor = User(email=f"doctor-{uuid4()}@example.com", password_hash="x", is_admin=True)
    db.add_all([coach, doctor])
    db.commit()
    service.review(
        analysis.id,
        coach.id,
        ReviewSubmission(
            role=BodyAnalysisReviewerRole.COACH,
            decision=BodyAnalysisReviewDecision.APPROVED,
            notes="Approved AI draft.",
        ),
    )

    corrected = service.review(
        analysis.id,
        doctor.id,
        ReviewSubmission(
            role=BodyAnalysisReviewerRole.DOCTOR,
            decision=BodyAnalysisReviewDecision.APPROVED,
            notes="Visibility is insufficient; correction recorded.",
            corrected_result=_normalized_payload(classification="uncertain"),
        ),
    )

    versions = db.scalars(
        select(BodyAnalysisResultVersion)
        .where(BodyAnalysisResultVersion.analysis_id == analysis.id)
        .order_by(BodyAnalysisResultVersion.version)
    ).all()
    reviews = db.scalars(
        select(BodyAnalysisReview).where(BodyAnalysisReview.analysis_id == analysis.id)
    ).all()
    effective = service.effective_result(session.id, user.id)
    assert [version.version for version in versions] == [1, 2]
    assert corrected.result_version_id == versions[1].id
    assert len(reviews) == 2
    assert effective.version == 2
    assert effective.normalized_result.summary.uncertain_areas == ("shoulders",)
    assert effective.fully_reviewed is False
    assert service.get_analysis(analysis.id, user.id).status is BodyAnalysisStatus.REVIEW_PENDING
