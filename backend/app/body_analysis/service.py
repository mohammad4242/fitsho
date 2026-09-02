from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
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
    normalize_visual_physique_assessment_v3,
    normalize_visual_physique_assessment_v4,
    visual_assessment_to_normalized,
    visual_assessment_v3_to_normalized,
    visual_assessment_v4_to_normalized,
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
    NormalizedBodyAnalysis,
    visual_physique_provider_schema,
    visual_physique_v3_provider_schema,
    visual_physique_v4_provider_schema,
)
from app.body_photos.enums import BodyPhotoSessionState, BodyPhotoView
from app.body_photos.models import BodyPhoto, BodyPhotoSession
from app.profile.enums import FitnessGoal, Sex
from app.profile.models import BodyMeasurement, UserProfile


class BodyAnalysisNotFoundError(LookupError):
    pass


class BodyAnalysisStateError(ValueError):
    pass


class BodyAnalysisInputError(ValueError):
    pass


class BodyAnalysisRequirementsError(BodyAnalysisInputError):
    def __init__(self, missing_fields: tuple[str, ...]) -> None:
        self.missing_fields = missing_fields
        super().__init__("required body analysis inputs are missing")


class BodyAnalysisConfirmationError(BodyAnalysisInputError):
    pass


class BodyAnalysisPhotoSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    view: BodyPhotoView
    photo_id: UUID
    storage_key: str = Field(min_length=1, max_length=160)
    updated_at: datetime


class BodyAnalysisInputSnapshot(BaseModel):
    """Immutable profile, measurement, and photo inputs captured at queue time."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    captured_at: datetime
    confirmed_at: datetime
    profile_updated_at: datetime
    measurement_id: UUID
    measurement_measured_at: datetime
    sex: Sex
    height_cm: int
    weight_kg: float
    shoulder_circumference_cm: float
    waist_circumference_cm: float
    hip_circumference_cm: float
    selected_goal: FitnessGoal
    photo_versions: tuple[BodyAnalysisPhotoSnapshot, ...] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_photo_versions(self) -> BodyAnalysisInputSnapshot:
        views = {photo.view for photo in self.photo_versions}
        if views != set(BodyPhotoView):
            raise ValueError("input snapshot must contain one photo for each view")
        return self


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
remaining strictly limited to what is visibly supported by the three user-selected headless body
photos standardized onto a neutral-gray background and labelled front, side, and back. Review all
views internally before producing JSON. Do not
reveal intermediate reasoning.

Provide a non-medical visual coaching assessment of visible muscular development, proportional
balance, shoulder-to-waist taper, upper-to-lower-body balance, and clearly visible left-right
differences. This is only a provisional input for future training personalization; never create a
workout program.

Do not infer age, sex, gender, identity, ethnicity, body-fat percentage, health, diagnosis, pain,
injury, mobility, physical strength, training history, genetics, the cause of an asymmetry, or
whether a visible difference persists outside the photo. Do not diagnose posture or a medical
condition. Do not recommend medical care, rehabilitation, exercises, sets, repetitions, loads,
frequency, or volume.

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

For each area, fill front, side, and back checklist items. Use excellent and good only when the
area is proportionally prominent relative to this same person's other visible areas; average when
it is assessable without a meaningful relative gap; needs_attention for a credible moderate
proportional gap; focus_priority for a clear actionable proportional gap; and not_assessable only
when that specific view cannot responsibly demonstrate the area. A view may be not_assessable
because it does not show the area naturally; this is not a failure. The overall rating must compare
the area with the person's full visible physique, cross-check usable views, and must not invent a
gap. Use focus_priority sparingly. A strong overall rating requires support in at least two views
when the area is visible in two views.
Do not return an all-uncertain result when multiple body regions are clearly visible.

For symmetry, report only obvious image-left versus image-right differences. Never call either
side the person's anatomical left or right. Ignore small differences reasonably explained by camera
angle, phone position, stance, rotation, or lighting. For visible_alignment_or_posture, describe
only a clear snapshot observation. Never name a condition, infer pain or mobility, explain the
cause, or claim persistence. Use neutral when there is no clear observation.

Return only valid JSON matching the supplied schema and do not add fields. Set assessment_status
to complete when all three views are usable and partial when exactly two are usable. In
photo_quality record each view's usable state and concise Persian limitations. In
overall_assessment provide the allowed proportional labels and a concise Persian summary. Return
exactly 13 findings using the prescribed area values. For every per-view and overall finding, write
concise, natural Persian evidence that names the visible comparison and its view; describe only
observable evidence and avoid motivational filler.

Use the supplied profile context only for the advisory goal_suggestion. Choose exactly one of
lose_weight, maintain_weight, build_muscle, or gain_weight. Respect the user's recorded goal as a
strong input but do not overwrite it. You may use available height, weight, shoulder, waist, and hip
measurements plus non-medical visible proportion observations. Never estimate body-fat percentage.
State missing inputs in inputs_unavailable_fa. The suggestion is advisory, not a diagnosis or a
prescription.

Only needs_attention and focus_priority may contain suggested_training_emphasis. Use only values
directly supported by the affected area: shoulders -> overall_shoulders, lateral_delts, and/or
rear_delts; chest -> overall_chest and/or upper_chest; back -> upper_back and/or mid_back; lats ->
lat_width; arms -> overall_arms, biceps, and/or triceps; forearms -> forearms; waist_midsection ->
trunk_musculature; glutes -> glutes; quads -> quads; hamstrings -> hamstrings; calves -> calves.
For symmetry use left_right_balance only when appropriate. For visible_alignment_or_posture leave
suggested_training_emphasis empty. Never provide exercises or programming instructions. The result
is provisional and requires human coach and doctor review."""

_ANALYSIS_V4_PROMPT = """You are Fitsho's evidence-only v4 body analysis assessor.
The supplied front, side, and back images have already passed Fitsho's local browser-side photo
validation and processing pipeline. Do not perform photo acceptance or preflight. Analyze the
supplied standardized images only for the structured physique evidence requested by the schema.
Return exactly one JSON object that matches the supplied schema. The response contains controlled
visual observations only: no free-form prose, messages, recommendations, diagnoses, posture claims,
pain or injury claims, body-composition estimates, genetic claims, or comparisons with other people.

Do not accept or reject entire photos, return photo-quality decisions, decide scan usability, or
decide whether enough views are usable. Use low evidence or not_assessable only for a specific
body-area observation when that observation cannot responsibly be evaluated. For this execution,
set assessment_status to complete.

Assess these eleven visible areas: shoulders, chest, back, lats, arms, forearms, waist_midsection,
glutes, quads, hamstrings, and calves. For each area choose only the supplied classification,
evidence strength, supporting view labels, observation tags, limitation codes, and supported
training-emphasis values. Add the controlled upper/lower balance and visible-symmetry states.
Use high evidence only when the relevant area is clearly supported by its required views. Use
not_assessable or low evidence when a responsible visual comparison is not possible. Never infer
sex, goals, measurements, health, posture, strength, training history, or future potential.
Do not include any field that is not declared by the schema."""

class BodyAnalysisService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def queue(
        self,
        session_id: UUID,
        user_id: UUID,
        config: AnalysisExecutionConfig,
        *,
        confirm_measurements_current: bool = False,
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
        input_snapshot = self._snapshot_for_creation(
            photo_session,
            config,
            replaces=latest,
            confirm_measurements_current=confirm_measurements_current,
        )
        return self._create_analysis(
            photo_session,
            config,
            replaces=latest,
            input_snapshot=input_snapshot,
        )

    def retry(
        self,
        analysis_id: UUID,
        user_id: UUID,
        config: AnalysisExecutionConfig,
        *,
        confirm_measurements_current: bool = False,
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
        input_snapshot = self._snapshot_for_creation(
            photo_session,
            config,
            replaces=latest,
            confirm_measurements_current=confirm_measurements_current,
        )
        return self._create_analysis(
            photo_session,
            config,
            replaces=latest,
            input_snapshot=input_snapshot,
        )

    def _snapshot_for_creation(
        self,
        photo_session: BodyPhotoSession,
        config: AnalysisExecutionConfig,
        *,
        replaces: BodyAnalysis | None,
        confirm_measurements_current: bool,
    ) -> BodyAnalysisInputSnapshot | None:
        if config.schema_version != "4.0":
            return None
        previous_snapshot = self._snapshot_from_analysis(replaces) if replaces else None
        if previous_snapshot is not None and self._photos_match_snapshot(
            photo_session.id, previous_snapshot
        ):
            return previous_snapshot
        if not confirm_measurements_current:
            raise BodyAnalysisConfirmationError(
                "current measurements must be confirmed after photo changes"
            )
        return self._capture_input_snapshot(photo_session)

    def _capture_input_snapshot(self, photo_session: BodyPhotoSession) -> BodyAnalysisInputSnapshot:
        captured_at = datetime.now(UTC)
        profile = self._db.scalar(
            select(UserProfile)
            .where(UserProfile.user_id == photo_session.user_id)
            .with_for_update()
        )
        measurement = self._db.scalar(
            select(BodyMeasurement)
            .where(BodyMeasurement.user_id == photo_session.user_id)
            .order_by(BodyMeasurement.measured_at.desc(), BodyMeasurement.id.desc())
            .with_for_update()
        )
        missing_fields: list[str] = []
        if profile is None or profile.sex is None:
            missing_fields.append("sex")
        if profile is None or profile.height_cm is None:
            missing_fields.append("height_cm")
        if measurement is None:
            missing_fields.extend(
                (
                    "weight_kg",
                    "shoulder_circumference_cm",
                    "waist_circumference_cm",
                    "hip_circumference_cm",
                )
            )
        else:
            if measurement.weight_kg is None:
                missing_fields.append("weight_kg")
            if measurement.shoulder_circumference_cm is None:
                missing_fields.append("shoulder_circumference_cm")
            if measurement.waist_circumference_cm is None:
                missing_fields.append("waist_circumference_cm")
            if measurement.hip_circumference_cm is None:
                missing_fields.append("hip_circumference_cm")
        if profile is None or profile.fitness_goal is None:
            missing_fields.append("fitness_goal")
        if missing_fields:
            raise BodyAnalysisRequirementsError(tuple(missing_fields))
        assert profile is not None
        assert measurement is not None
        assert measurement.shoulder_circumference_cm is not None
        assert measurement.waist_circumference_cm is not None
        assert measurement.hip_circumference_cm is not None
        return BodyAnalysisInputSnapshot(
            captured_at=captured_at,
            confirmed_at=captured_at,
            profile_updated_at=profile.updated_at,
            measurement_id=measurement.id,
            measurement_measured_at=measurement.measured_at,
            sex=profile.sex,
            height_cm=profile.height_cm,
            weight_kg=float(measurement.weight_kg),
            shoulder_circumference_cm=float(measurement.shoulder_circumference_cm),
            waist_circumference_cm=float(measurement.waist_circumference_cm),
            hip_circumference_cm=float(measurement.hip_circumference_cm),
            selected_goal=profile.fitness_goal,
            photo_versions=tuple(
                BodyAnalysisPhotoSnapshot(
                    view=photo.view,
                    photo_id=photo.id,
                    storage_key=photo.storage_key,
                    updated_at=photo.updated_at,
                )
                for photo in self._photos_for_session(photo_session.id)
            ),
        )

    def _photos_for_session(self, session_id: UUID) -> tuple[BodyPhoto, ...]:
        return tuple(
            self._db.scalars(
                select(BodyPhoto)
                .where(BodyPhoto.session_id == session_id)
                .order_by(BodyPhoto.view)
            ).all()
        )

    def _photos_match_snapshot(
        self,
        session_id: UUID,
        snapshot: BodyAnalysisInputSnapshot,
    ) -> bool:
        current = self._photos_for_session(session_id)
        current_by_view = {
            photo.view: (photo.id, photo.storage_key, photo.updated_at) for photo in current
        }
        expected_by_view = {
            photo.view: (photo.photo_id, photo.storage_key, photo.updated_at)
            for photo in snapshot.photo_versions
        }
        return current_by_view == expected_by_view

    @staticmethod
    def _snapshot_from_analysis(
        analysis: BodyAnalysis | None,
    ) -> BodyAnalysisInputSnapshot | None:
        if analysis is None or not isinstance(analysis.raw_result, dict):
            return None
        raw_snapshot = analysis.raw_result.get("input_snapshot")
        if not isinstance(raw_snapshot, dict):
            return None
        try:
            return BodyAnalysisInputSnapshot.model_validate(raw_snapshot)
        except ValidationError:
            return None

    @classmethod
    def _snapshot_profile_context(
        cls,
        analysis: BodyAnalysis,
    ) -> dict[str, object]:
        snapshot = cls._snapshot_from_analysis(analysis)
        if snapshot is None:
            raise BodyAnalysisInputError("analysis input snapshot is missing")
        return {
            "selected_goal": snapshot.selected_goal.value,
            "height_cm": snapshot.height_cm,
            "weight_kg": snapshot.weight_kg,
            "shoulder_circumference_cm": snapshot.shoulder_circumference_cm,
            "waist_circumference_cm": snapshot.waist_circumference_cm,
            "hip_circumference_cm": snapshot.hip_circumference_cm,
        }

    @staticmethod
    def _raw_result_with(
        body_analysis: BodyAnalysis,
        **entries: object,
    ) -> dict[str, object]:
        raw_result = (
            deepcopy(body_analysis.raw_result)
            if isinstance(body_analysis.raw_result, dict)
            else {}
        )
        raw_result.update(entries)
        return raw_result

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
                    # A provider change starts a new bounded recovery scope;
                    # previous provider attempts remain immutable history.
                    BodyAnalysis.provider == config.provider_name,
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
        input_snapshot: BodyAnalysisInputSnapshot | None,
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
            cycle_id=photo_session.cycle_id,
            session_id=photo_session.id,
            replaces_analysis_id=replaces.id if replaces else None,
            revision=revision,
            provider=config.provider_name,
            model_id=config.primary_model,
            fallback_model_id=(config.fallback_models[0] if config.fallback_models else None),
            prompt_version=config.prompt_version,
            schema_version=config.schema_version,
            status=BodyAnalysisStatus.QUEUED,
            raw_result=(
                {"input_snapshot": input_snapshot.model_dump(mode="json")}
                if input_snapshot is not None
                else None
            ),
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
        try:
            if (
                execution_config.schema_version == "4.0"
                and self._snapshot_from_analysis(analysis) is None
            ):
                raise BodyAnalysisInputError("analysis input snapshot is missing")
            analysis.attempt_count += 1
            analysis.started_at = datetime.now(UTC)
            images = self._prepare_images(analysis)
            image_inputs = self._image_inputs(images)
            analysis.status = BodyAnalysisStatus.ANALYZING
            analysis.session.state = BodyPhotoSessionState.ANALYZING
            self._db.commit()

            response = await provider.analyze_images(
                self._request(
                    execution_config,
                    profile_context=(
                        None
                        if execution_config.schema_version == "4.0"
                        else self._profile_context(analysis.session.user_id)
                    ),
                ),
                images=image_inputs,
            )
            visual_result = None
            if execution_config.schema_version == "2.0":
                visual_v2 = normalize_visual_physique_assessment(response.payload)
                normalized = visual_assessment_to_normalized(visual_v2)
                visual_result = visual_v2.model_dump(mode="json")
            elif execution_config.schema_version == "3.0":
                visual_v3 = normalize_visual_physique_assessment_v3(response.payload)
                normalized = visual_assessment_v3_to_normalized(visual_v3)
                visual_result = visual_v3.model_dump(mode="json")
            elif execution_config.schema_version == "4.0":
                evidence = normalize_visual_physique_assessment_v4(response.payload)
                if evidence.assessment_status != "complete":
                    raise BodyAnalysisInputError("unexpected v4 assessment status")
                try:
                    normalized = visual_assessment_v4_to_normalized(evidence)
                except ValueError as error:
                    raise BodyAnalysisInputError("v4 evidence projection failed") from error
            else:
                normalized = normalize_body_analysis(response.payload)
            if normalized.schema_version != execution_config.schema_version:
                raise BodyAnalysisInputError("unexpected analysis schema version")
            if normalized.overall_confidence < execution_config.minimum_confidence:
                raise BodyAnalysisInputError(
                    "analysis confidence is below the configured threshold"
                )
            self._validate_response_cost(response, execution_config)
            analysis.raw_result = self._raw_result_with(
                analysis,
                analysis=response.payload,
            )
            analysis.normalized_result = normalized.model_dump(mode="json")
            analysis.visual_result = visual_result
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
        if {photo.view for photo in photos} != set(BodyPhotoView):
            raise BodyAnalysisInputError("three standardized headless views are required")
        return photos

    def _image_inputs(
        self, images: tuple[BodyPhoto, ...]
    ) -> tuple[ImageInput, ...]:
        return tuple(
            ImageInput(
                label=photo.view.value,
                mime_type=photo.mime_type,
                storage_scope="body",
                storage_key=photo.storage_key,
            )
            for photo in images
        )

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
    def _request(
        config: AnalysisExecutionConfig,
        *,
        profile_context: dict[str, object] | None = None,
    ) -> StructuredGenerationRequest:
        input_payload: dict[str, object] = {
            "task": "analyze_processed_body_views",
            "schema_version": config.schema_version,
        }
        if profile_context is not None:
            input_payload["profile_context"] = profile_context
        return StructuredGenerationRequest(
            system_prompt=(
                _ANALYSIS_V4_PROMPT
                if config.schema_version == "4.0"
                else _ANALYSIS_PROMPT
            ),
            input_payload=input_payload,
            response_schema=(
                visual_physique_provider_schema()
                if config.schema_version == "2.0"
                else visual_physique_v3_provider_schema()
                if config.schema_version == "3.0"
                else visual_physique_v4_provider_schema()
                if config.schema_version == "4.0"
                else NormalizedBodyAnalysis.model_json_schema()
            ),
            schema_name=(
                "fitsho_physique_assessment_v2"
                if config.schema_version == "2.0"
                else "fitsho_physique_assessment_v3"
                if config.schema_version == "3.0"
                else "fitsho_body_analysis_v4_evidence"
                if config.schema_version == "4.0"
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

    def _profile_context(self, user_id: UUID) -> dict[str, object]:
        profile = self._db.get(UserProfile, user_id)
        if profile is None or profile.fitness_goal is None:
            return {}
        measurement = self._db.scalar(
            select(BodyMeasurement)
            .where(BodyMeasurement.user_id == user_id)
            .order_by(BodyMeasurement.measured_at.desc(), BodyMeasurement.id.desc())
        )
        if measurement is None:
            return {
                "selected_goal": profile.fitness_goal.value,
                "height_cm": profile.height_cm,
            }
        return {
            "selected_goal": profile.fitness_goal.value,
            "height_cm": profile.height_cm,
            "weight_kg": float(measurement.weight_kg),
            "shoulder_circumference_cm": (
                float(measurement.shoulder_circumference_cm)
                if measurement.shoulder_circumference_cm is not None
                else None
            ),
            "waist_circumference_cm": (
                float(measurement.waist_circumference_cm)
                if measurement.waist_circumference_cm is not None
                else None
            ),
            "hip_circumference_cm": (
                float(measurement.hip_circumference_cm)
                if measurement.hip_circumference_cm is not None
                else None
            ),
        }

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
                "The configured AI provider credential was rejected. "
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
