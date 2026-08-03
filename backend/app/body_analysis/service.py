from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import BinaryIO, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.body_analysis.comparison_service import BodyProgressComparisonService
from app.body_analysis.enums import (
    BodyAnalysisResultSource,
    BodyAnalysisReviewDecision,
    BodyAnalysisReviewerRole,
    BodyAnalysisStatus,
)
from app.body_analysis.models import (
    BodyAnalysis,
    BodyAnalysisResultVersion,
    BodyAnalysisReview,
    UserSpecialistRole,
)
from app.body_analysis.normalization import (
    MedicalClaimError,
    normalize_body_analysis,
    normalize_visual_physique_assessment,
    visual_assessment_to_normalized,
)
from app.body_analysis.providers import (
    AIProvider,
    AIProviderError,
    ImageInput,
    ModelRoute,
    ProviderErrorCode,
    ProviderRoutingPreferences,
    StructuredGenerationRequest,
    StructuredGenerationResponse,
)
from app.body_analysis.schemas import (
    BodyPhotoPreflight,
    BodyPhotoValidationIssue,
    NormalizedBodyAnalysis,
    visual_physique_provider_schema,
)
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
    timeout_seconds: int = Field(default=45, ge=1, le=180)
    retry_limit: int = Field(default=2, ge=0, le=5)
    minimum_confidence: float = Field(default=0.7, ge=0, le=1)
    max_cost_per_request: Decimal | None = Field(default=None, ge=0)
    routing_preferences: ProviderRoutingPreferences = Field(
        default_factory=ProviderRoutingPreferences
    )


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


_ANALYSIS_PROMPT = """You are Fitsho's conservative visual physique-development assessor.
Reproduce the structured visual review process of an experienced in-person physique coach while
remaining strictly limited to what is visibly supported by the three processed, head-cropped body
photos labelled front, side, and back. Review all views internally before producing JSON. Do not
reveal intermediate reasoning.

Provide a non-medical visual coaching assessment of visible muscular development, proportional
balance, shoulder-to-waist taper, upper-to-lower-body balance, and clearly visible left-right
differences. This is only a provisional input for future training personalization; never create a
workout program.

Do not infer age, sex, gender, identity, ethnicity, body-fat percentage, health, diagnosis, pain,
injury, mobility, physical strength, training history, genetics, the cause of an asymmetry, or
whether a visible difference persists outside the photo. Do not diagnose posture or a medical
condition. Do not recommend medical care, rehabilitation, exercises, sets, repetitions, loads,
frequency, or volume. A classification of strength means only visually more developed or
proportionally prominent relative to this person's other visible body areas; it never means actual
physical strength.

Compare areas primarily with this same person's other visible areas, never with the general
population, athletes, fitness models, ideals, or demographic groups. Use visible size, contour,
width, thickness, and proportion. Do not require sharp definition, separation, vascularity, or low
body fat to make a relative visual assessment. Soft definition alone is never a reason to use
uncertain. Use uncertain only when framing, clothing, lighting, perspective, pose, or occlusion
genuinely prevents a responsible comparison. When an area appears in multiple views, cross-check
it and prefer the clearest, most neutral view. Do not invent findings. Use neutral when an area is
assessable but has no meaningful relative strength or lag.

Scan these areas in this exact order: shoulders, chest, back, lats, arms, forearms,
waist_midsection, glutes, quads, hamstrings, calves, symmetry, visible_alignment_or_posture.
In the front view assess shoulder width and deltoids, chest, arms and forearms, waist, quads,
calves, and visible image-left versus image-right differences. In the side view assess chest depth,
arm profile, torso-to-waist proportion, glute profile, quad and hamstring profile, and calf
profile. A phone is a limitation only when it materially hides the relevant tissue. In the back
view assess rear delts, upper and mid-back thickness, lat width, arms, waist taper, glutes,
hamstrings, calves, and visible side-to-side differences.

Classify every area exactly once. Use strength only when it is visibly more developed or
proportionally prominent relative to this person's other assessable areas. Use neutral when it is
assessable with no meaningful relative strength or lag. Use mild_lag for a smaller but credible
proportional gap. Use clear_lag sparingly for a noticeable, actionable proportional gap, normally
supported by two views when the area is visible in two views. Use uncertain only when it cannot be
responsibly compared from the available views. Do not return an all-uncertain result when multiple
body regions are clearly visible. Do not force strengths or lags: a genuinely balanced visible area
is neutral.

For symmetry, report only obvious image-left versus image-right differences. Never call either
side the person's anatomical left or right. Ignore small differences reasonably explained by camera
angle, phone position, stance, rotation, or lighting. For visible_alignment_or_posture, describe
only a clear snapshot observation. Never name a condition, infer pain or mobility, explain the
cause, or claim persistence. Use neutral when there is no clear observation.

Return only valid JSON matching the supplied schema and do not add fields. Set assessment_status
to complete when all three views are usable and partial when exactly two are usable. In
photo_quality record each view's usable state and concise Persian limitations. In
overall_assessment provide the allowed proportional labels and a concise Persian summary. Return
exactly 13 findings using these
area values: shoulders, chest, back, lats, arms, forearms, waist_midsection, glutes, quads,
hamstrings, calves, symmetry, visible_alignment_or_posture. For every finding, write evidence_fa in
concise, natural Persian. Name the visible comparison and supporting view or views, describe only
observable evidence, and avoid motivational filler. For mild_lag and clear_lag set severity between
0 and 1; for strength, neutral, uncertain, and not_assessable set severity to null.

Only mild_lag and clear_lag may contain suggested_training_emphasis. Use only values directly
supported by the affected area: shoulders -> overall_shoulders, lateral_delts, and/or rear_delts;
chest -> overall_chest and/or upper_chest; back -> upper_back and/or mid_back; lats -> lat_width;
arms -> overall_arms, biceps, and/or triceps; forearms -> forearms; waist_midsection ->
trunk_musculature; glutes -> glutes; quads -> quads; hamstrings -> hamstrings; calves -> calves.
For symmetry use left_right_balance only when it is a lag. For visible_alignment_or_posture leave
suggested_training_emphasis empty. Never provide exercises or programming instructions. The result
is provisional and requires human coach and doctor review."""

_PHOTO_PREFLIGHT_PROMPT = """You validate three processed, head-cropped body photos before
any body-development analysis. Check each labelled view for exactly one visible person, full
body framing, the requested view, usable lighting, adequate sharpness, clothing that does not
obscure body contours, and a background that does not materially obstruct the body. Fitted
athletic shorts or underwear are acceptable when the torso, arms, legs, and visible body
contours remain clear; do not reject them merely for being fitted or dark. Do not reject a photo
merely because its background is a gym or a room, contains equipment, furniture, a bed, a mirror,
or is visually cluttered. A mirror selfie is acceptable when exactly one full body is clearly
visible; a phone is acceptable when it does not cover relevant body regions. Reject background
only when people or objects materially hide body regions or make the requested view ambiguous.
Count only real people in the foreground: ignore people shown in posters, wall art, mirrors, gym
branding, screens, or other background imagery. Do not infer nudity, identity, health, or body
composition. Reject only when the evidence clearly fails a listed requirement; when uncertain,
use photo_uncertain rather than guessing. Set accepted to true when at least two views are usable;
when one view is unusable, include its view-specific reasons in issues so the later assessment can
be partial. Set accepted to false only when fewer than two views are usable. Return only the
requested JSON."""


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
        if latest is not None:
            self._assert_retry_available(photo_session.id, config)
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
        if latest is None or latest.id != previous.id:
            raise BodyAnalysisStateError("only the latest analysis revision can be retried")
        if latest.status in {
            BodyAnalysisStatus.QUEUED,
            BodyAnalysisStatus.VALIDATING,
            BodyAnalysisStatus.ANALYZING,
        }:
            if not self._is_stale(latest, config):
                return latest
            latest.status = BodyAnalysisStatus.FAILED
            latest.error_code = ProviderErrorCode.TIMEOUT.value
            latest.error_message = "Body analysis could not be completed. Please retry later."
            latest.completed_at = datetime.now(UTC)
            self._db.commit()
        elif latest.status is not BodyAnalysisStatus.FAILED:
            raise BodyAnalysisStateError("only failed or stale analyses can be retried")
        self._assert_retry_available(photo_session.id, config)
        return self._create_analysis(photo_session, config, replaces=latest)

    def _assert_retry_available(
        self,
        session_id: UUID,
        config: AnalysisExecutionConfig,
    ) -> None:
        latest_photo_change = (
            select(func.max(BodyPhoto.updated_at))
            .where(BodyPhoto.session_id == session_id)
            .scalar_subquery()
        )
        attempts = int(
            self._db.scalar(
                select(func.count())
                .select_from(BodyAnalysis)
                .where(
                    BodyAnalysis.session_id == session_id,
                    BodyAnalysis.created_at >= latest_photo_change,
                )
            )
            or 0
        )
        if attempts >= config.retry_limit + 1:
            raise BodyAnalysisStateError("analysis retry limit reached")

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
        photo_session.state = BodyPhotoSessionState.QUEUED
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
        response: StructuredGenerationResponse | None = None
        preflight_response: StructuredGenerationResponse | None = None
        try:
            analysis.status = BodyAnalysisStatus.VALIDATING
            analysis.attempt_count += 1
            analysis.started_at = datetime.now(UTC)
            analysis.session.state = BodyPhotoSessionState.VALIDATING
            self._db.commit()
            images = self._prepare_images(analysis)
            image_inputs = self._image_inputs(storage, images)
            preflight_response = await provider.analyze_images(
                self._preflight_request(execution_config),
                images=image_inputs,
            )
            preflight = BodyPhotoPreflight.model_validate(preflight_response.payload)
            if preflight.accepted and preflight.confidence < execution_config.minimum_confidence:
                preflight = BodyPhotoPreflight(
                    accepted=False,
                    confidence=preflight.confidence,
                    issues=tuple(
                        BodyPhotoValidationIssue(view=photo.view, reasons=("photo_uncertain",))
                        for photo in images
                    ),
                )
            self._validate_response_cost(preflight_response, execution_config)
            if not preflight.accepted:
                self._record_photo_rejection(analysis, preflight, preflight_response)
                return self._analysis(analysis_id)
            rejected_views = {issue.view for issue in preflight.issues}
            analysis_images = tuple(
                image for image in image_inputs if BodyPhotoView(image.label) not in rejected_views
            )
            if len(analysis_images) < 2:
                raise BodyAnalysisInputError("fewer than two photos are usable for analysis")
            analysis.status = BodyAnalysisStatus.ANALYZING
            analysis.session.state = BodyPhotoSessionState.ANALYZING
            self._db.commit()

            response = await provider.analyze_images(
                self._request(execution_config),
                images=analysis_images,
            )
            visual_result = None
            if execution_config.schema_version == "2.0":
                visual = normalize_visual_physique_assessment(response.payload)
                normalized = visual_assessment_to_normalized(visual)
                visual_result = visual.model_dump(mode="json")
            else:
                normalized = normalize_body_analysis(response.payload)
            if normalized.schema_version != execution_config.schema_version:
                raise BodyAnalysisInputError("unexpected analysis schema version")
            if normalized.overall_confidence < execution_config.minimum_confidence:
                raise BodyAnalysisInputError(
                    "analysis confidence is below the configured threshold"
                )
            self._validate_response_cost(response, execution_config)
            analysis.raw_result = {
                "photo_validation": preflight.model_dump(mode="json"),
                "analysis": response.payload,
            }
            analysis.normalized_result = normalized.model_dump(mode="json")
            analysis.visual_result = visual_result
            analysis.overall_confidence = normalized.overall_confidence
            analysis.model_id = response.model_id
            analysis.provider_request_id = response.provider_request_id
            analysis.input_tokens = self._sum_optional_int(
                preflight_response.input_tokens, response.input_tokens
            )
            analysis.output_tokens = self._sum_optional_int(
                preflight_response.output_tokens, response.output_tokens
            )
            analysis.request_cost = self._sum_optional_decimal(
                preflight_response.cost, response.cost
            )
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
                    visual_result=visual_result,
                    overall_confidence=normalized.overall_confidence,
                )
            )
            self._db.commit()
            result_version = self._current_version(analysis.id)
            if result_version is not None:
                try:
                    BodyProgressComparisonService(self._db).create_for_result(
                        result_version.id,
                        analysis.session.user_id,
                    )
                except Exception:
                    # Comparisons are optional history. A comparison failure must
                    # never discard a valid analysis or prevent plan generation.
                    self._db.rollback()
        except Exception as error:
            self._db.rollback()
            analysis = self._analysis(analysis_id, lock=True)
            provider_error = self._safe_provider_error(provider, error)
            if response is not None:
                # Preserve provider accounting even if output validation or a
                # configured cost ceiling rejects the result. This makes later
                # billing reconciliation possible without retaining raw photos.
                analysis.model_id = response.model_id
                analysis.provider_request_id = response.provider_request_id
                analysis.input_tokens = response.input_tokens
                analysis.output_tokens = response.output_tokens
                analysis.request_cost = response.cost
            elif preflight_response is not None:
                analysis.model_id = preflight_response.model_id
                analysis.provider_request_id = preflight_response.provider_request_id
                analysis.input_tokens = preflight_response.input_tokens
                analysis.output_tokens = preflight_response.output_tokens
                analysis.request_cost = preflight_response.cost
            analysis.status = BodyAnalysisStatus.FAILED
            analysis.error_code = provider_error.code.value
            analysis.error_message = self._safe_failure_message(provider_error.code)
            if provider_error.provider_request_id is not None:
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
        self._authorize_reviewer(reviewer_id, submission.role)
        if analysis.status not in {
            BodyAnalysisStatus.REVIEW_PENDING,
            BodyAnalysisStatus.COMPLETED,
        }:
            raise BodyAnalysisStateError("analysis is not ready for specialist review")
        current = self._current_version(analysis.id)
        if current is None:
            raise BodyAnalysisStateError("analysis has no normalized result")
        other_role = (
            BodyAnalysisReviewerRole.DOCTOR
            if submission.role is BodyAnalysisReviewerRole.COACH
            else BodyAnalysisReviewerRole.COACH
        )
        other_approval = self._db.scalar(
            select(BodyAnalysisReview).where(
                BodyAnalysisReview.analysis_id == analysis.id,
                BodyAnalysisReview.result_version_id == current.id,
                BodyAnalysisReview.reviewer_role == other_role,
                BodyAnalysisReview.reviewer_id == reviewer_id,
                BodyAnalysisReview.decision == BodyAnalysisReviewDecision.APPROVED,
            )
        )
        if (
            other_approval is not None
            and submission.decision is BodyAnalysisReviewDecision.APPROVED
        ):
            raise BodyAnalysisStateError("one reviewer cannot approve both specialist roles")
        if submission.corrected_result is not None:
            corrected = normalize_body_analysis(submission.corrected_result)
            replacement = BodyAnalysisResultVersion(
                analysis_id=analysis.id,
                replaces_version_id=current.id,
                version=current.version + 1,
                source=BodyAnalysisResultSource(submission.role.value),
                normalized_result=corrected.model_dump(mode="json"),
                visual_result=current.visual_result,
                overall_confidence=corrected.overall_confidence,
                created_by_user_id=reviewer_id,
            )
            self._db.add(replacement)
            self._db.flush()
            current = replacement
            analysis.normalized_result = corrected.model_dump(mode="json")
            analysis.visual_result = current.visual_result
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

    def _image_inputs(
        self, storage: BodyAnalysisReadStorage, images: tuple[BodyPhoto, ...]
    ) -> tuple[ImageInput, ...]:
        return tuple(
            ImageInput(
                label=photo.view.value,
                mime_type=photo.mime_type,
                base64_data=base64.b64encode(self._read(storage, photo.storage_key)).decode(),
            )
            for photo in images
        )

    def _record_photo_rejection(
        self,
        analysis: BodyAnalysis,
        preflight: BodyPhotoPreflight,
        response: StructuredGenerationResponse,
    ) -> None:
        analysis.raw_result = {"photo_validation": preflight.model_dump(mode="json")}
        analysis.model_id = response.model_id
        analysis.provider_request_id = response.provider_request_id
        analysis.input_tokens = response.input_tokens
        analysis.output_tokens = response.output_tokens
        analysis.request_cost = response.cost
        analysis.status = BodyAnalysisStatus.FAILED
        analysis.error_code = "photo_validation_failed"
        analysis.error_message = "Your photos need to be retaken. Review the view-specific reasons."
        analysis.completed_at = datetime.now(UTC)
        analysis.session.state = self._session_state_after_failure(analysis)
        self._db.commit()

    @staticmethod
    def _validate_response_cost(
        response: StructuredGenerationResponse, config: AnalysisExecutionConfig
    ) -> None:
        if (
            config.max_cost_per_request is not None
            and response.cost is not None
            and response.cost > config.max_cost_per_request
        ):
            raise BodyAnalysisInputError("analysis cost exceeds the configured limit")

    @staticmethod
    def _sum_optional_int(left: int | None, right: int | None) -> int | None:
        if left is None and right is None:
            return None
        return (left or 0) + (right or 0)

    @staticmethod
    def _sum_optional_decimal(left: Decimal | None, right: Decimal | None) -> Decimal | None:
        if left is None and right is None:
            return None
        return (left or Decimal("0")) + (right or Decimal("0"))

    @staticmethod
    def _request(config: AnalysisExecutionConfig) -> StructuredGenerationRequest:
        return StructuredGenerationRequest(
            system_prompt=_ANALYSIS_PROMPT,
            input_payload={
                "task": "analyze_processed_body_views",
                "schema_version": config.schema_version,
            },
            response_schema=(
                visual_physique_provider_schema()
                if config.schema_version == "2.0"
                else NormalizedBodyAnalysis.model_json_schema()
            ),
            schema_name=(
                "fitsho_physique_assessment_v2"
                if config.schema_version == "2.0"
                else "fitsho_body_analysis"
            ),
            route=ModelRoute(
                primary_model=config.primary_model,
                fallback_models=config.fallback_models,
            ),
            provider_preferences=config.routing_preferences,
            temperature=config.temperature,
            max_output_tokens=config.max_output_tokens,
        )

    @staticmethod
    def _preflight_request(config: AnalysisExecutionConfig) -> StructuredGenerationRequest:
        return StructuredGenerationRequest(
            system_prompt=_PHOTO_PREFLIGHT_PROMPT,
            input_payload={"task": "validate_processed_body_views"},
            response_schema=BodyPhotoPreflight.model_json_schema(),
            schema_name="fitsho_body_photo_preflight",
            route=ModelRoute(
                primary_model=config.primary_model,
                fallback_models=config.fallback_models,
            ),
            provider_preferences=config.routing_preferences,
            temperature=0,
            max_output_tokens=min(config.max_output_tokens, 900),
        )

    @staticmethod
    def _safe_provider_error(provider: AIProvider, error: Exception) -> AIProviderError:
        if isinstance(error, (ValidationError, MedicalClaimError, BodyAnalysisInputError)):
            return AIProviderError(
                ProviderErrorCode.INVALID_OUTPUT,
                "The provider response did not match the body-analysis contract.",
            )
        return provider.normalize_error(error)

    @staticmethod
    def _safe_failure_message(code: ProviderErrorCode) -> str:
        if code is ProviderErrorCode.UNAUTHORIZED:
            return (
                "The OpenRouter API key for body analysis was rejected. "
                "Update it in Admin AI settings."
            )
        if code is ProviderErrorCode.INVALID_OUTPUT:
            return (
                "The selected AI model returned an invalid structured response. "
                "Choose another image and Structured Output capable model, add a fallback, "
                "or raise the output-token limit."
            )
        return "Body analysis could not be completed. Please retry later."

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

    def _authorize_reviewer(self, reviewer_id: UUID, role: BodyAnalysisReviewerRole) -> None:
        allowed = self._db.scalar(
            select(UserSpecialistRole).where(
                UserSpecialistRole.user_id == reviewer_id,
                UserSpecialistRole.role == role.value,
            )
        )
        if allowed is None:
            raise BodyAnalysisStateError("reviewer is not authorized for this specialist role")

    @staticmethod
    def _is_stale(analysis: BodyAnalysis, config: AnalysisExecutionConfig) -> bool:
        if analysis.started_at is None:
            return analysis.created_at <= datetime.now(UTC) - timedelta(
                seconds=config.timeout_seconds
            )
        return analysis.started_at <= datetime.now(UTC) - timedelta(seconds=config.timeout_seconds)
