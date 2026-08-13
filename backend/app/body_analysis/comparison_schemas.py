from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.body_analysis.comparison_enums import BodyProgressState
from app.body_analysis.enums import BodyAnalysisClassification, BodyArea
from app.body_photos.enums import BodyPhotoView


class BodyProgressAreaComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    body_area: BodyArea
    state: BodyProgressState
    previous_classification: BodyAnalysisClassification | None
    current_classification: BodyAnalysisClassification | None
    change_confidence: float = Field(ge=0, le=1)
    supporting_views: tuple[BodyPhotoView, ...] = ()
    explanation: str = Field(min_length=1, max_length=500)
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_unique_evidence(self) -> BodyProgressAreaComparison:
        if len(set(self.supporting_views)) != len(self.supporting_views):
            raise ValueError("supporting views must be unique")
        if len(set(self.limitations)) != len(self.limitations):
            raise ValueError("limitations must be unique")
        return self


class NormalizedBodyProgressComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    overall_confidence: float = Field(ge=0, le=1)
    previous_session_id: UUID
    current_session_id: UUID
    previous_result_version_id: UUID
    current_result_version_id: UUID
    areas: tuple[BodyProgressAreaComparison, ...] = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_unique_areas(self) -> NormalizedBodyProgressComparison:
        if self.previous_session_id == self.current_session_id:
            raise ValueError("comparison sessions must be different")
        if len({area.body_area for area in self.areas}) != len(self.areas):
            raise ValueError("each body area may appear at most once")
        return self


class ComparisonInputQuality(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    analysis_confidence: float = Field(ge=0, le=1)
    all_standardized_views_present: bool


class UserReportedMeasurementChange(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    previous: float
    current: float
    delta: float


class BodyProgressComparisonContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    previous_feedback_id: UUID | None = None
    current_feedback_id: UUID | None = None
    previous_adherence_percent: int | None = Field(default=None, ge=0, le=100)
    current_adherence_percent: int | None = Field(default=None, ge=0, le=100)
    previous_performance_feedback_available: bool = False
    current_performance_feedback_available: bool = False
    current_pain_or_limitation_feedback_available: bool = False
    user_reported_measurement_changes: dict[str, UserReportedMeasurementChange] = Field(
        default_factory=dict
    )


class BodyProgressComparisonResponse(BaseModel):
    id: UUID
    previous_session_id: UUID
    current_session_id: UUID
    previous_result_version_id: UUID
    current_result_version_id: UUID
    comparison_version: int
    schema_version: str
    normalized_result: NormalizedBodyProgressComparison
    quality_snapshot: dict[str, ComparisonInputQuality]
    context_snapshot: BodyProgressComparisonContext
    created_at: datetime
