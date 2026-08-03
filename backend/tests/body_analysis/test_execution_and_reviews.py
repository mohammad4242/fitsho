from __future__ import annotations

import asyncio
import io
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.body_analysis.admin_config.enums import AIProviderName, AITaskType
from app.body_analysis.admin_config.models import AIModelCatalogEntry, AITaskConfig
from app.body_analysis.enums import (
    BodyAnalysisReviewDecision,
    BodyAnalysisReviewerRole,
    BodyAnalysisStatus,
    SpecialistRole,
)
from app.body_analysis.models import (
    BodyAnalysis,
    BodyAnalysisResultVersion,
    BodyAnalysisReview,
    UserSpecialistRole,
)
from app.body_analysis.providers import (
    AIProviderError,
    ProviderErrorCode,
    StructuredGenerationResponse,
)
from app.body_analysis.runtime import _validate_budget_preflight
from app.body_analysis.service import (
    AnalysisExecutionConfig,
    BodyAnalysisService,
    BodyAnalysisStateError,
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


def _grant(db: Session, user: User, role: SpecialistRole) -> None:
    db.add(UserSpecialistRole(user_id=user.id, role=role))
    db.commit()


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


def test_execution_creates_a_progress_comparison_for_the_new_result(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user, session = _submitted_session(db)
    service = BodyAnalysisService(db)
    analysis = service.queue(session.id, user.id, _config())
    calls: list[tuple[object, object]] = []

    class _ComparisonService:
        def __init__(self, comparison_db: Session) -> None:
            assert comparison_db is db

        def create_for_result(self, result_version_id: object, owner_id: object) -> None:
            calls.append((result_version_id, owner_id))

    monkeypatch.setattr(
        "app.body_analysis.service.BodyProgressComparisonService",
        _ComparisonService,
    )

    asyncio.run(service.execute(analysis.id, _Provider(), _Storage()))

    assert calls and calls[0][1] == user.id


def test_completed_analysis_cannot_be_retried(db: Session) -> None:
    user, session = _submitted_session(db)
    service = BodyAnalysisService(db)
    successful = service.queue(session.id, user.id, _config())
    asyncio.run(service.execute(successful.id, _Provider(), _Storage()))

    with pytest.raises(BodyAnalysisStateError, match="only failed or stale"):
        service.retry(successful.id, user.id, _config())


def test_coach_and_doctor_approvals_are_independent_and_version_bound(db: Session) -> None:
    user, session = _submitted_session(db)
    service = BodyAnalysisService(db)
    analysis = service.queue(session.id, user.id, _config())
    asyncio.run(service.execute(analysis.id, _Provider(), _Storage()))
    coach = User(email=f"coach-{uuid4()}@example.com", password_hash="x", is_admin=True)
    doctor = User(email=f"doctor-{uuid4()}@example.com", password_hash="x", is_admin=True)
    db.add_all([coach, doctor])
    db.commit()
    _grant(db, coach, SpecialistRole.COACH)
    _grant(db, doctor, SpecialistRole.DOCTOR)

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
    _grant(db, coach, SpecialistRole.COACH)
    _grant(db, doctor, SpecialistRole.DOCTOR)
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


def test_same_user_cannot_satisfy_coach_and_doctor_approvals(db: Session) -> None:
    user, session = _submitted_session(db)
    service = BodyAnalysisService(db)
    analysis = service.queue(session.id, user.id, _config())
    asyncio.run(service.execute(analysis.id, _Provider(), _Storage()))
    reviewer = User(email=f"dual-{uuid4()}@example.com", password_hash="x")
    db.add(reviewer)
    db.commit()
    _grant(db, reviewer, SpecialistRole.COACH)
    _grant(db, reviewer, SpecialistRole.DOCTOR)
    service.review(
        analysis.id,
        reviewer.id,
        ReviewSubmission(
            role=BodyAnalysisReviewerRole.COACH,
            decision=BodyAnalysisReviewDecision.APPROVED,
        ),
    )

    with pytest.raises(BodyAnalysisStateError, match="cannot approve both"):
        service.review(
            analysis.id,
            reviewer.id,
            ReviewSubmission(
                role=BodyAnalysisReviewerRole.DOCTOR,
                decision=BodyAnalysisReviewDecision.APPROVED,
            ),
        )


def test_stale_analysis_is_recovered_but_retry_attempts_are_bounded(db: Session) -> None:
    user, session = _submitted_session(db)
    service = BodyAnalysisService(db)
    config = _config().model_copy(update={"retry_limit": 1, "timeout_seconds": 1})
    first = service.queue(session.id, user.id, config)
    first.status = BodyAnalysisStatus.ANALYZING
    first.started_at = datetime.now(UTC) - timedelta(seconds=2)
    db.commit()

    recovered = service.retry(first.id, user.id, config)

    assert recovered.id != first.id
    assert recovered.revision == 2
    assert recovered.replaces_analysis_id == first.id
    db.refresh(session)
    assert session.state is BodyPhotoSessionState.QUEUED
    recovered.status = BodyAnalysisStatus.FAILED
    db.commit()
    with pytest.raises(BodyAnalysisStateError, match="retry limit"):
        service.retry(recovered.id, user.id, config)


def test_low_confidence_and_cost_limited_results_fail_safely(db: Session) -> None:
    user, session = _submitted_session(db)
    service = BodyAnalysisService(db)
    config = _config().model_copy(
        update={"minimum_confidence": 0.9, "max_cost_per_request": Decimal("0.01")}
    )
    analysis = service.queue(session.id, user.id, config)

    failed = asyncio.run(service.execute(analysis.id, _Provider(), _Storage(), config))

    assert failed.status is BodyAnalysisStatus.FAILED
    assert failed.error_message == "Body analysis could not be completed. Please retry later."


def test_rejected_cost_is_retained_for_billing_reconciliation(db: Session) -> None:
    user, session = _submitted_session(db)
    service = BodyAnalysisService(db)
    config = _config().model_copy(update={"max_cost_per_request": Decimal("0.01")})
    analysis = service.queue(session.id, user.id, config)

    failed = asyncio.run(service.execute(analysis.id, _Provider(), _Storage(), config))

    assert failed.status is BodyAnalysisStatus.FAILED
    assert failed.request_cost == Decimal("0.012")
    assert failed.input_tokens == 100
    assert failed.output_tokens == 200


def test_fresh_queued_analysis_is_not_considered_stale(db: Session) -> None:
    user, session = _submitted_session(db)
    service = BodyAnalysisService(db)
    config = _config().model_copy(update={"timeout_seconds": 1})
    queued = service.queue(session.id, user.id, config)

    assert service.retry(queued.id, user.id, config).id == queued.id


def test_normal_queue_path_respects_retry_limit(db: Session) -> None:
    user, session = _submitted_session(db)
    service = BodyAnalysisService(db)
    config = _config().model_copy(update={"retry_limit": 0})
    failed = service.queue(session.id, user.id, config)
    failed.status = BodyAnalysisStatus.FAILED
    db.commit()

    with pytest.raises(BodyAnalysisStateError, match="retry limit"):
        service.queue(session.id, user.id, config)


def test_retry_rejects_nonlatest_revision(db: Session) -> None:
    user, session = _submitted_session(db)
    service = BodyAnalysisService(db)
    initial = service.queue(session.id, user.id, _config())
    initial.status = BodyAnalysisStatus.FAILED
    db.commit()
    replacement = service.retry(initial.id, user.id, _config())

    with pytest.raises(BodyAnalysisStateError, match="latest analysis revision"):
        service.retry(initial.id, user.id, _config())
    assert replacement.replaces_analysis_id == initial.id


def test_provider_request_id_survives_post_response_validation_error(db: Session) -> None:
    user, session = _submitted_session(db)
    service = BodyAnalysisService(db)
    analysis = service.queue(session.id, user.id, _config())
    malformed_schema = {**_normalized_payload(), "schema_version": "9.9"}

    failed = asyncio.run(service.execute(analysis.id, _Provider(malformed_schema), _Storage()))

    assert failed.status is BodyAnalysisStatus.FAILED
    assert failed.provider_request_id == "req-safe-id"


def test_cost_ceiling_preflight_fails_closed_without_complete_catalog_pricing(db: Session) -> None:
    task = AITaskConfig(
        task_type=AITaskType.BODY_PHOTO_ANALYSIS,
        provider=AIProviderName.OPENROUTER,
        primary_model_id="vision-model",
        enabled=True,
        max_output_tokens=100,
        max_cost_per_request=Decimal("0.00001"),
    )
    db.add(task)
    db.commit()

    with pytest.raises(ValueError, match="cannot evaluate"):
        _validate_budget_preflight(db, task)

    db.add(
        AIModelCatalogEntry(
            provider=AIProviderName.OPENROUTER,
            model_id="vision-model",
            display_name="Vision",
            provider_family="vendor",
            supports_text_input=True,
            supports_image_input=True,
            supports_structured_output=True,
            context_length=200,
            input_price_per_token=Decimal("0.00001"),
            output_price_per_token=Decimal("0.00001"),
            refreshed_at=datetime.now(UTC),
        )
    )
    db.commit()
    with pytest.raises(ValueError, match="cost ceiling"):
        _validate_budget_preflight(db, task)
