from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.body_analysis.enums import (
    BodyAnalysisResultSource,
    BodyAnalysisReviewDecision,
    BodyAnalysisReviewerRole,
    BodyAnalysisStatus,
    BodyArea,
)
from app.body_analysis.schemas import (
    BodyPhotoPreflight,
    NormalizedBodyAnalysis,
    VisualPhysiqueAssessment,
    VisualPhysiqueAssessmentV3,
)
from app.body_photos.enums import BodyPhotoView
from app.profile.enums import FitnessGoal, Sex


class BodyAnalysisStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm_measurements_current: Literal[True]


class BodyAnalysisInputSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

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


class BodyAnalysisExperienceMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_key: str
    parameters: dict[str, object] = Field(default_factory=dict)


class BodyAnalysisExperienceDirection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["aligned_with_current_goal", "goal_confirmation_required"]
    goal: FitnessGoal | None
    reason_codes: tuple[str, ...]


class BodyAnalysisExperienceIndicator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    message_key: str
    parameters: dict[str, object] = Field(default_factory=dict)
    score_percent: int | None = Field(default=None, ge=0, le=100)


class BodyAnalysisExperienceIndicators(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upper_lower_balance: BodyAnalysisExperienceIndicator
    visible_symmetry: BodyAnalysisExperienceIndicator
    body_shape: BodyAnalysisExperienceIndicator


class BodyAnalysisExperienceRegion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    area: BodyArea
    display_classification: Literal[
        "stronger",
        "balanced",
        "room_to_grow",
        "primary_priority",
        "not_assessable",
    ]
    insight_key: str | None
    insight_parameters: dict[str, object] = Field(default_factory=dict)
    supporting_views: tuple[BodyPhotoView, ...]


class BodyAnalysisExperienceV4(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["4.0"]
    presentation_version: Literal["body-analysis-experience-v2"]
    assessment_status: Literal["complete", "partial"]
    input_snapshot: BodyAnalysisInputSnapshotResponse
    first_impression: BodyAnalysisExperienceMessage
    direction: BodyAnalysisExperienceDirection
    indicators: BodyAnalysisExperienceIndicators
    regions: tuple[BodyAnalysisExperienceRegion, ...] = Field(min_length=11, max_length=11)
    review_notice_code: str


class SpecialistReviewState(BaseModel):
    role: BodyAnalysisReviewerRole
    decision: BodyAnalysisReviewDecision | None
    reviewed_at: datetime | None
    reviewed_result_version: int | None


class BodyAnalysisResponse(BaseModel):
    id: UUID
    cycle_id: UUID | None
    session_id: UUID
    revision: int
    status: BodyAnalysisStatus
    provider: str
    model_id: str
    schema_version: str
    result_version: int | None
    result_source: BodyAnalysisResultSource | None
    normalized_result: NormalizedBodyAnalysis | None
    visual_result: VisualPhysiqueAssessment | VisualPhysiqueAssessmentV3 | None
    experience_result: BodyAnalysisExperienceV4 | None
    overall_confidence: float | None
    coach_review: SpecialistReviewState
    doctor_review: SpecialistReviewState
    fully_reviewed: bool
    unverified_warning: bool
    error_code: str | None
    safe_error_message: str | None
    photo_validation: BodyPhotoPreflight | None
    created_at: datetime
    completed_at: datetime | None


class SpecialistReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: BodyAnalysisReviewerRole
    decision: BodyAnalysisReviewDecision
    notes: str | None = Field(default=None, min_length=1, max_length=2000)
    corrected_result: dict[str, object] | None = None


class SpecialistReviewResponse(BaseModel):
    id: UUID
    analysis_id: UUID
    result_version_id: UUID
    reviewer_id: UUID
    role: BodyAnalysisReviewerRole
    decision: BodyAnalysisReviewDecision
    notes: str | None
    reviewed_at: datetime


class BodyAnalysisResultVersionResponse(BaseModel):
    id: UUID
    version: int
    source: BodyAnalysisResultSource
    normalized_result: NormalizedBodyAnalysis
    visual_result: VisualPhysiqueAssessment | VisualPhysiqueAssessmentV3 | None
    overall_confidence: float
    created_by_user_id: UUID | None
    created_at: datetime


class BodyAnalysisReviewHistoryResponse(SpecialistReviewResponse):
    result_version: int


class BodyAnalysisReviewDetail(BaseModel):
    analysis: BodyAnalysisResponse
    result_versions: list[BodyAnalysisResultVersionResponse]
    reviews: list[BodyAnalysisReviewHistoryResponse]
