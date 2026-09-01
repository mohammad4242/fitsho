from __future__ import annotations

import asyncio
import inspect
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
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
    StructuredGenerationRequest,
    StructuredGenerationResponse,
)
from app.body_analysis.runtime import _validate_budget_preflight
from app.body_analysis.service import (
    _ANALYSIS_PROMPT,
    _PHOTO_PREFLIGHT_PROMPT,
    AnalysisExecutionConfig,
    BodyAnalysisService,
    BodyAnalysisStateError,
    ReviewSubmission,
)
from app.body_photos.enums import BodyPhotoPurpose, BodyPhotoSessionState, BodyPhotoView
from app.body_photos.models import BodyPhoto, BodyPhotoSession
from app.profile.enums import FitnessGoal, Sex
from app.profile.models import BodyMeasurement, UserProfile


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


def _v4_evidence_payload() -> dict[str, object]:
    areas = (
        "shoulders",
        "chest",
        "back",
        "lats",
        "arms",
        "forearms",
        "waist_midsection",
        "glutes",
        "quads",
        "hamstrings",
        "calves",
    )
    return {
        "schema_version": "4.0",
        "assessment_status": "complete",
        "area_observations": [
            {
                "area": area,
                "classification": "balanced",
                "evidence_strength": "moderate",
                "supporting_views": ["front", "side"],
                "observation_tags": ["relative_width"],
                "limitation_codes": [],
                "suggested_training_emphasis": [],
            }
            for area in areas
        ],
        "upper_lower_balance": {
            "state": "balanced",
            "evidence_strength": "moderate",
            "supporting_views": ["front", "side"],
        },
        "visible_symmetry": {
            "state": "no_clear_difference",
            "evidence_strength": "moderate",
            "supporting_views": ["front", "back"],
        },
    }


class _Provider:
    def __init__(self, payload: dict[str, object] | None = None) -> None:
        self.payload = payload or _normalized_payload()
        self.calls = 0
        self.requests: list[StructuredGenerationRequest] = []
        self.images: list[tuple[object, ...]] = []

    async def analyze_images(self, request: object, *, images: tuple[object, ...]) -> object:
        self.calls += 1
        self.requests.append(cast(StructuredGenerationRequest, request))
        self.images.append(images)
        assert len(images) == 3
        assert all(getattr(image, "base64_data", None) is None for image in images)
        assert all(getattr(image, "storage_scope", None) == "body" for image in images)
        assert all(getattr(image, "storage_key", None) for image in images)
        payload = (
            {"accepted": True, "confidence": 0.92, "issues": []}
            if getattr(request, "schema_name", None) == "fitsho_body_photo_preflight"
            else self.payload
        )
        return StructuredGenerationResponse(
            payload=payload,
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


class _CostlessProvider(_Provider):
    def __init__(self) -> None:
        super().__init__()
        self.schema_names: list[str] = []

    async def analyze_images(self, request: object, *, images: tuple[object, ...]) -> object:
        self.schema_names.append(cast(StructuredGenerationRequest, request).schema_name)
        response = await super().analyze_images(request, images=images)
        assert isinstance(response, StructuredGenerationResponse)
        return response.model_copy(update={"cost": None})


class _V4Provider(_Provider):
    def __init__(self) -> None:
        super().__init__(_v4_evidence_payload())


class _FailingProvider(_Provider):
    async def analyze_images(self, request: object, *, images: tuple[object, ...]) -> object:
        self.calls += 1
        raise AIProviderError(
            ProviderErrorCode.UNAUTHORIZED,
            "The AI provider credential was rejected.",
        )


class _PreflightRejectingProvider(_Provider):
    async def analyze_images(self, request: object, *, images: tuple[object, ...]) -> object:
        self.calls += 1
        return StructuredGenerationResponse(
            payload={
                "accepted": False,
                "confidence": 0.94,
                "issues": [
                    {"view": "front", "reasons": ["full_body_not_visible", "low_lighting"]},
                    {"view": "side", "reasons": ["low_lighting"]},
                ],
            },
            model_id="vision-primary",
            attempted_models=("vision-primary",),
            provider_request_id="req-preflight",
            input_tokens=80,
            output_tokens=60,
            cost=Decimal("0.004"),
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


def _v4_config() -> AnalysisExecutionConfig:
    return _config().model_copy(
        update={"prompt_version": "body-analysis-v4-evidence", "schema_version": "4.0"}
    )


def _complete_body_profile(db: Session, user: User) -> UserProfile:
    profile = UserProfile(
        user_id=user.id,
        sex=Sex.MALE,
        height_cm=178,
        fitness_goal=FitnessGoal.BUILD_MUSCLE,
    )
    measurement = BodyMeasurement(
        user_id=user.id,
        weight_kg=Decimal("82.5"),
        shoulder_circumference_cm=Decimal("122"),
        waist_circumference_cm=Decimal("84"),
        hip_circumference_cm=Decimal("98"),
    )
    db.add_all([profile, measurement])
    db.commit()
    db.refresh(profile)
    return profile


def test_v4_queue_accepts_explicit_measurement_confirmation() -> None:
    assert "confirm_measurements_current" in inspect.signature(BodyAnalysisService.queue).parameters


def test_v4_queue_captures_profile_measurement_and_photo_snapshot(db: Session) -> None:
    user, session = _submitted_session(db)
    _complete_body_profile(db, user)

    analysis = BodyAnalysisService(db).queue(
        session.id,
        user.id,
        _v4_config(),
        confirm_measurements_current=True,
    )

    assert isinstance(analysis.raw_result, dict)
    snapshot = analysis.raw_result["input_snapshot"]
    assert isinstance(snapshot, dict)
    assert snapshot["sex"] == "male"
    assert snapshot["height_cm"] == 178
    assert snapshot["weight_kg"] == 82.5
    assert snapshot["shoulder_circumference_cm"] == 122.0
    assert snapshot["waist_circumference_cm"] == 84.0
    assert snapshot["hip_circumference_cm"] == 98.0
    assert snapshot["selected_goal"] == "build_muscle"
    assert {photo["view"] for photo in snapshot["photo_versions"]} == {
        "front",
        "side",
        "back",
    }


@pytest.mark.parametrize(
    "missing_field",
    [
        "sex",
        "height_cm",
        "weight_kg",
        "shoulder_circumference_cm",
        "waist_circumference_cm",
        "hip_circumference_cm",
        "fitness_goal",
    ],
)
def test_v4_queue_rejects_each_missing_required_input(
    db: Session,
    missing_field: str,
) -> None:
    user, session = _submitted_session(db)
    profile = _complete_body_profile(db, user)
    if missing_field in {"sex", "height_cm", "fitness_goal"}:
        setattr(profile, missing_field, None)
    else:
        measurement = db.scalar(
            select(BodyMeasurement).where(BodyMeasurement.user_id == user.id)
        )
        assert measurement is not None
        if missing_field == "weight_kg":
            db.delete(measurement)
        else:
            setattr(measurement, missing_field, None)
    db.commit()

    with pytest.raises(ValueError, match="required body analysis inputs"):
        BodyAnalysisService(db).queue(
            session.id,
            user.id,
            _v4_config(),
            confirm_measurements_current=True,
        )


@pytest.mark.parametrize("sex", [Sex.OTHER, Sex.PREFER_NOT_TO_SAY])
def test_v4_queue_accepts_neutral_sex_values(db: Session, sex: Sex) -> None:
    user, session = _submitted_session(db)
    profile = _complete_body_profile(db, user)
    profile.sex = sex
    db.commit()

    analysis = BodyAnalysisService(db).queue(
        session.id,
        user.id,
        _v4_config(),
        confirm_measurements_current=True,
    )

    assert analysis.raw_result["input_snapshot"]["sex"] == sex.value


def test_v4_execution_uses_the_queued_snapshot_after_profile_changes(db: Session) -> None:
    user, session = _submitted_session(db)
    profile = _complete_body_profile(db, user)
    analysis = BodyAnalysisService(db).queue(
        session.id,
        user.id,
        _v4_config(),
        confirm_measurements_current=True,
    )
    measurement = db.scalar(
        select(BodyMeasurement).where(BodyMeasurement.user_id == user.id)
    )
    assert measurement is not None
    profile.height_cm = 190
    measurement.weight_kg = Decimal("91.0")
    db.commit()

    provider = _Provider()
    asyncio.run(BodyAnalysisService(db).execute(analysis.id, provider, _v4_config()))

    assert len(provider.requests) == 2
    assert provider.requests[1].input_payload == {
        "task": "analyze_processed_body_views",
        "schema_version": "4.0",
    }


def test_v4_retry_without_photo_changes_reuses_the_original_snapshot(db: Session) -> None:
    user, session = _submitted_session(db)
    _complete_body_profile(db, user)
    service = BodyAnalysisService(db)
    config = _v4_config()
    first = service.queue(session.id, user.id, config, confirm_measurements_current=True)
    first.status = BodyAnalysisStatus.FAILED
    db.commit()

    replacement = service.retry(first.id, user.id, config)

    assert replacement.raw_result == first.raw_result


def test_v4_retry_after_photo_change_requires_fresh_confirmation(db: Session) -> None:
    user, session = _submitted_session(db)
    _complete_body_profile(db, user)
    service = BodyAnalysisService(db)
    config = _v4_config()
    first = service.queue(session.id, user.id, config, confirm_measurements_current=True)
    first.status = BodyAnalysisStatus.FAILED
    db.commit()
    changed_photo = session.photos[0]
    changed_photo.storage_key = f"bb/{uuid4().hex}.jpg"
    changed_photo.updated_at = datetime.now(UTC) + timedelta(seconds=1)
    db.commit()

    with pytest.raises(ValueError, match="current measurements must be confirmed"):
        service.retry(first.id, user.id, config)

    replacement = service.retry(
        first.id,
        user.id,
        config,
        confirm_measurements_current=True,
    )

    assert replacement.raw_result != first.raw_result
    previous_keys = {
        photo["view"]: photo["storage_key"]
        for photo in first.raw_result["input_snapshot"]["photo_versions"]
    }
    replacement_keys = {
        photo["view"]: photo["storage_key"]
        for photo in replacement.raw_result["input_snapshot"]["photo_versions"]
    }
    assert replacement_keys[changed_photo.view.value] != previous_keys[changed_photo.view.value]


def test_v4_snapshot_survives_preflight_rejection(db: Session) -> None:
    user, session = _submitted_session(db)
    _complete_body_profile(db, user)
    config = _v4_config()
    service = BodyAnalysisService(db)
    analysis = service.queue(session.id, user.id, config, confirm_measurements_current=True)

    failed = asyncio.run(service.execute(analysis.id, _PreflightRejectingProvider(), config))

    assert failed.status is BodyAnalysisStatus.FAILED
    assert isinstance(failed.raw_result, dict)
    assert "input_snapshot" in failed.raw_result
    assert "photo_validation" in failed.raw_result


def test_v4_snapshot_survives_provider_failure(db: Session) -> None:
    user, session = _submitted_session(db)
    _complete_body_profile(db, user)
    config = _v4_config()
    service = BodyAnalysisService(db)
    analysis = service.queue(session.id, user.id, config, confirm_measurements_current=True)

    failed = asyncio.run(service.execute(analysis.id, _FailingProvider(), config))

    assert failed.status is BodyAnalysisStatus.FAILED
    assert isinstance(failed.raw_result, dict)
    assert "input_snapshot" in failed.raw_result


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


def test_photo_preflight_ignores_people_in_background_artwork() -> None:
    request = BodyAnalysisService._preflight_request(_config())
    normalized_prompt = " ".join(request.system_prompt.split())

    assert "posters, wall art, mirrors, gym branding" in normalized_prompt
    assert "Count only real people in the foreground" in normalized_prompt


def test_execution_persists_validated_result_and_is_idempotent(db: Session) -> None:
    user, session = _submitted_session(db)
    provider = _Provider()
    service = BodyAnalysisService(db)
    analysis = service.queue(session.id, user.id, _config())

    completed = asyncio.run(service.execute(analysis.id, provider))
    repeated = asyncio.run(service.execute(analysis.id, provider))

    assert completed.status is BodyAnalysisStatus.REVIEW_PENDING
    assert repeated.id == completed.id
    assert provider.calls == 2
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


def test_v4_execution_persists_evidence_projection_without_legacy_visual_result(
    db: Session,
) -> None:
    user, session = _submitted_session(db)
    _complete_body_profile(db, user)
    config = _v4_config()
    analysis = BodyAnalysisService(db).queue(
        session.id,
        user.id,
        config,
        confirm_measurements_current=True,
    )

    completed = asyncio.run(BodyAnalysisService(db).execute(analysis.id, _V4Provider(), config))

    assert completed.status is BodyAnalysisStatus.REVIEW_PENDING
    assert completed.schema_version == "4.0"
    assert completed.visual_result is None
    assert completed.normalized_result is not None
    assert completed.normalized_result["schema_version"] == "4.0"
    assert completed.raw_result["analysis"]["schema_version"] == "4.0"


def test_execution_uses_one_provider_for_preflight_and_analysis_without_cost(db: Session) -> None:
    user, session = _submitted_session(db)
    provider = _CostlessProvider()
    config = _config().model_copy(update={"max_cost_per_request": Decimal("0.01")})
    service = BodyAnalysisService(db)
    analysis = service.queue(session.id, user.id, config)

    completed = asyncio.run(service.execute(analysis.id, provider, config))

    assert completed.status is BodyAnalysisStatus.REVIEW_PENDING
    assert provider.schema_names == ["fitsho_body_photo_preflight", "fitsho_body_analysis"]
    assert provider.calls == 2
    assert completed.request_cost is None


def test_body_requests_and_processed_image_labels_are_backend_independent(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: list[
        tuple[list[StructuredGenerationRequest], list[tuple[object, ...]], dict[str, str]]
    ] = []
    profile_context = {
        "selected_goal": "build_muscle",
        "height_cm": 178,
        "weight_kg": 82.5,
    }
    monkeypatch.setattr(
        BodyAnalysisService,
        "_profile_context",
        lambda _self, _user_id: profile_context,
    )

    for provider_name in ("openrouter", "agent_service:antigravity"):
        user, session = _submitted_session(db)
        provider = _Provider()
        config = _config().model_copy(update={"provider_name": provider_name})
        analysis = BodyAnalysisService(db).queue(session.id, user.id, config)

        completed = asyncio.run(BodyAnalysisService(db).execute(analysis.id, provider, config))

        assert completed.status is BodyAnalysisStatus.REVIEW_PENDING
        captured.append(
            (
                provider.requests,
                provider.images,
                {photo.view.value: photo.storage_key for photo in session.photos},
            )
        )

    api_requests, api_images, api_keys = captured[0]
    agent_requests, agent_images, agent_keys = captured[1]
    assert [request.model_dump() for request in api_requests] == [
        request.model_dump() for request in agent_requests
    ]
    for image_batches, keys in ((api_images, api_keys), (agent_images, agent_keys)):
        for image_batch in image_batches:
            expected_views = tuple(sorted(keys))
            assert [
                (image.label, image.mime_type, image.storage_scope, image.storage_key)
                for image in image_batch
            ] == [
                (view, "image/jpeg", "body", keys[view]) for view in expected_views
            ]
    assert [request.system_prompt for request in api_requests] == [
        _PHOTO_PREFLIGHT_PROMPT,
        _ANALYSIS_PROMPT,
    ]
    assert api_requests[1].input_payload["profile_context"] == profile_context


def test_execution_stops_after_rejected_photo_preflight_and_preserves_view_reasons(
    db: Session,
) -> None:
    user, session = _submitted_session(db)
    provider = _PreflightRejectingProvider()
    analysis = BodyAnalysisService(db).queue(session.id, user.id, _config())

    failed = asyncio.run(BodyAnalysisService(db).execute(analysis.id, provider))

    assert failed.status is BodyAnalysisStatus.FAILED
    assert provider.calls == 1
    assert failed.raw_result == {
        "photo_validation": {
            "accepted": False,
            "confidence": 0.94,
            "issues": [
                {"view": "front", "reasons": ["full_body_not_visible", "low_lighting"]},
                {"view": "side", "reasons": ["low_lighting"]},
            ],
        },
    }


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

    asyncio.run(service.execute(analysis.id, _Provider()))

    assert calls and calls[0][1] == user.id


def test_completed_analysis_cannot_be_retried(db: Session) -> None:
    user, session = _submitted_session(db)
    service = BodyAnalysisService(db)
    successful = service.queue(session.id, user.id, _config())
    asyncio.run(service.execute(successful.id, _Provider()))

    with pytest.raises(BodyAnalysisStateError, match="only failed or stale"):
        service.retry(successful.id, user.id, _config())


def test_coach_and_doctor_approvals_are_independent_and_version_bound(db: Session) -> None:
    user, session = _submitted_session(db)
    service = BodyAnalysisService(db)
    analysis = service.queue(session.id, user.id, _config())
    asyncio.run(service.execute(analysis.id, _Provider()))
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
    asyncio.run(service.execute(analysis.id, _Provider()))
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
    asyncio.run(service.execute(analysis.id, _Provider()))
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

    failed = asyncio.run(service.execute(analysis.id, _Provider(), config))

    assert failed.status is BodyAnalysisStatus.FAILED
    assert "invalid structured response" in (failed.error_message or "")


def test_unauthorized_provider_error_tells_admin_to_update_configured_credentials(
    db: Session,
) -> None:
    user, session = _submitted_session(db)
    analysis = BodyAnalysisService(db).queue(session.id, user.id, _config())

    failed = asyncio.run(
        BodyAnalysisService(db).execute(analysis.id, _FailingProvider())
    )

    assert failed.status is BodyAnalysisStatus.FAILED
    assert failed.error_code == "unauthorized"
    assert (
        failed.error_message
        == "The configured AI provider credential was rejected. Update it in Admin AI settings."
    )


def test_invalid_model_output_tells_admin_how_to_correct_the_ai_task(db: Session) -> None:
    service = BodyAnalysisService(db)

    message = service._safe_failure_message(ProviderErrorCode.INVALID_OUTPUT)

    assert message == (
        "The selected AI model returned an invalid structured response. "
        "Choose another image and Structured Output capable model, add a fallback, "
        "or raise the output-token limit."
    )


def test_rejected_cost_is_retained_for_billing_reconciliation(db: Session) -> None:
    user, session = _submitted_session(db)
    service = BodyAnalysisService(db)
    config = _config().model_copy(update={"max_cost_per_request": Decimal("0.01")})
    analysis = service.queue(session.id, user.id, config)

    failed = asyncio.run(service.execute(analysis.id, _Provider(), config))

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


def test_replacing_a_photo_resets_the_analysis_retry_budget(db: Session) -> None:
    user, session = _submitted_session(db)
    service = BodyAnalysisService(db)
    config = _config().model_copy(update={"retry_limit": 0})
    failed = service.queue(session.id, user.id, config)
    failed.status = BodyAnalysisStatus.FAILED
    db.commit()

    replacement = session.photos[0]
    replacement.updated_at = datetime.now(UTC) + timedelta(seconds=1)
    db.commit()

    retried = service.queue(session.id, user.id, config)

    assert retried.revision == 2
    assert retried.replaces_analysis_id == failed.id


def test_photo_preflight_allows_fitted_clothing_and_nonblocking_backgrounds() -> None:
    normalized_prompt = " ".join(_PHOTO_PREFLIGHT_PROMPT.split())

    assert "Fitted athletic shorts or underwear are acceptable" in normalized_prompt
    assert "performed by the user before upload" in normalized_prompt
    assert "must never trigger full_body_not_visible" in normalized_prompt
    assert "Do not reject a photo merely because its background is a gym or a room" in (
        normalized_prompt
    )


def test_analysis_prompt_requires_a_full_schema_compatible_coach_scan() -> None:
    normalized_prompt = " ".join(_ANALYSIS_PROMPT.split())

    assert "Return exactly 13 findings" in normalized_prompt
    assert "visible_alignment_or_posture" in normalized_prompt
    assert "not_assessable" in normalized_prompt
    assert "photo_quality" in normalized_prompt
    assert "all-uncertain" in normalized_prompt
    assert "natural Persian" in normalized_prompt


def test_v2_provider_schema_avoids_structured_output_state_explosion() -> None:
    request = BodyAnalysisService._request(
        AnalysisExecutionConfig(
            provider_name="openrouter",
            primary_model="google/gemini-2.5-flash",
            prompt_version="body-analysis-v2",
            schema_version="2.0",
        )
    )
    serialized = json.dumps(request.response_schema)

    assert "maxItems" not in serialized
    assert "minItems" not in serialized
    assert '"minimum"' not in serialized
    assert '"maximum"' not in serialized


def test_v3_provider_request_includes_advisory_profile_context() -> None:
    request = BodyAnalysisService._request(
        AnalysisExecutionConfig(
            provider_name="openrouter",
            primary_model="google/gemini-2.5-flash",
            prompt_version="body-analysis-v3",
            schema_version="3.0",
        ),
        profile_context={
            "selected_goal": "build_muscle",
            "height_cm": 178,
            "weight_kg": 76.5,
            "shoulder_circumference_cm": 122.0,
            "waist_circumference_cm": 84.0,
            "hip_circumference_cm": 98.0,
        },
    )

    assert request.input_payload["profile_context"] == {
        "selected_goal": "build_muscle",
        "height_cm": 178,
        "weight_kg": 76.5,
        "shoulder_circumference_cm": 122.0,
        "waist_circumference_cm": 84.0,
        "hip_circumference_cm": 98.0,
    }


def test_v4_provider_request_is_evidence_only() -> None:
    request = BodyAnalysisService._request(_v4_config())

    assert request.schema_name == "fitsho_body_analysis_v4_evidence"
    assert request.input_payload == {
        "task": "analyze_processed_body_views",
        "schema_version": "4.0",
    }
    assert request.system_prompt.startswith("You are Fitsho's evidence-only v4 body analysis")


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

    failed = asyncio.run(service.execute(analysis.id, _Provider(malformed_schema)))

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


def test_zero_cost_ceiling_means_no_cost_limit(db: Session) -> None:
    task = AITaskConfig(
        task_type=AITaskType.BODY_PHOTO_ANALYSIS,
        provider=AIProviderName.OPENROUTER,
        primary_model_id="vision-model",
        enabled=True,
        max_cost_per_request=Decimal("0"),
    )
    db.add(task)
    db.commit()

    _validate_budget_preflight(db, task)
