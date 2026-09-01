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
)
from app.body_analysis.schemas import (
    BodyPhotoPreflight,
    NormalizedBodyAnalysis,
    VisualPhysiqueAssessment,
    VisualPhysiqueAssessmentV3,
)


class BodyAnalysisStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm_measurements_current: Literal[True]


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
