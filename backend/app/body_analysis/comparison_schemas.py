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


BodyProgressMeasurementName = Literal[
    "weight_kg",
    "shoulder_circumference_cm",
    "waist_circumference_cm",
    "hip_circumference_cm",
]
BodyProgressMeasurementUnit = Literal["kg", "cm"]
BodyProgressProvenanceSource = Literal[
    "body_analysis_input_snapshot",
    "cycle_measurement",
    "normalized_result",
    "unavailable",
]
BodyProgressProvenanceReasonCode = Literal[
    "exact_analysis_input_snapshot",
    "exact_cycle_measurement",
    "measurement_unavailable_for_legacy_scan",
    "effective_normalized_result",
]
BodyProgressVisualReasonCode = Literal[
    "classification_changed",
    "classification_unchanged",
    "missing_previous_observation",
    "missing_current_observation",
    "incomplete_standardized_views",
    "no_common_supporting_view",
    "low_confidence",
    "specialist_corrected_result",
]


class BodyProgressProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: BodyProgressProvenanceSource
    reference_id: UUID | None = None
    recorded_at: datetime | None = None
    reason_code: BodyProgressProvenanceReasonCode

    @model_validator(mode="after")
    def validate_reference(self) -> BodyProgressProvenance:
        if self.source == "unavailable":
            if self.reference_id is not None or self.recorded_at is not None:
                raise ValueError("unavailable provenance cannot contain a reference")
            if self.reason_code != "measurement_unavailable_for_legacy_scan":
                raise ValueError("unavailable provenance requires an unavailable reason")
        elif self.reference_id is None or self.recorded_at is None:
            raise ValueError("available provenance requires a reference and timestamp")
        return self


class BodyProgressItemProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    previous: BodyProgressProvenance
    current: BodyProgressProvenance


class BodyProgressMeasurementDelta(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    measurement: BodyProgressMeasurementName
    unit: BodyProgressMeasurementUnit
    previous: float | None
    current: float | None
    delta: float | None
    availability: Literal["exact", "unavailable"]
    provenance: BodyProgressItemProvenance

    @model_validator(mode="after")
    def validate_delta(self) -> BodyProgressMeasurementDelta:
        if self.measurement == "weight_kg" and self.unit != "kg":
            raise ValueError("weight must use kilograms")
        if self.measurement != "weight_kg" and self.unit != "cm":
            raise ValueError("circumferences must use centimeters")
        if self.availability == "exact":
            if self.previous is None or self.current is None or self.delta is None:
                raise ValueError("exact measurements require both values and a delta")
            if (
                self.provenance.previous.source == "unavailable"
                or self.provenance.current.source == "unavailable"
            ):
                raise ValueError("exact measurements require available provenance")
        elif self.delta is not None:
            raise ValueError("unavailable measurements cannot expose a delta")
        return self


class BodyProgressVisualTransition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    body_area: BodyArea
    state: BodyProgressState
    previous_classification: BodyAnalysisClassification | None
    current_classification: BodyAnalysisClassification | None
    change_confidence: float = Field(ge=0, le=1)
    supporting_views: tuple[BodyPhotoView, ...] = ()
    reason_codes: tuple[BodyProgressVisualReasonCode, ...] = Field(min_length=1)
    provenance: BodyProgressItemProvenance

    @model_validator(mode="after")
    def validate_unique_values(self) -> BodyProgressVisualTransition:
        if len(set(self.supporting_views)) != len(self.supporting_views):
            raise ValueError("supporting views must be unique")
        if len(set(self.reason_codes)) != len(self.reason_codes):
            raise ValueError("visual reason codes must be unique")
        return self


class BodyProgressPersistentPriority(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    body_area: BodyArea
    provenance: BodyProgressItemProvenance


class NormalizedBodyProgressComparisonV2(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["2.0"] = "2.0"
    overall_confidence: float = Field(ge=0, le=1)
    previous_session_id: UUID
    current_session_id: UUID
    previous_result_version_id: UUID
    current_result_version_id: UUID
    previous_session_date: datetime
    current_session_date: datetime
    interval_days: int = Field(ge=0)
    measurement_deltas: tuple[BodyProgressMeasurementDelta, ...] = Field(
        min_length=4, max_length=4
    )
    visual_transitions: tuple[BodyProgressVisualTransition, ...] = Field(min_length=1)
    persistent_priorities: tuple[BodyProgressPersistentPriority, ...] = ()
    measurement_notice_code: Literal["measurements_recorded_by_user"] = (
        "measurements_recorded_by_user"
    )
    visual_observation_notice_code: Literal[
        "standardized_photo_observation_not_direct_measurement"
    ] = "standardized_photo_observation_not_direct_measurement"

    @model_validator(mode="after")
    def validate_unique_values(self) -> NormalizedBodyProgressComparisonV2:
        if self.previous_session_id == self.current_session_id:
            raise ValueError("comparison sessions must be different")
        if self.current_session_date < self.previous_session_date:
            raise ValueError("current comparison session must not precede previous session")
        if len({item.measurement for item in self.measurement_deltas}) != 4:
            raise ValueError("all four measurements must appear exactly once")
        if len({item.body_area for item in self.visual_transitions}) != len(
            self.visual_transitions
        ):
            raise ValueError("each visual body area may appear at most once")
        if len({item.body_area for item in self.persistent_priorities}) != len(
            self.persistent_priorities
        ):
            raise ValueError("persistent priorities must be unique")
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
    normalized_result: NormalizedBodyProgressComparison | NormalizedBodyProgressComparisonV2
    quality_snapshot: dict[str, ComparisonInputQuality]
    context_snapshot: BodyProgressComparisonContext
    created_at: datetime
