from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.body_analysis.comparison_schemas import NormalizedBodyProgressComparison
from app.body_analysis.enums import BodyArea


class BodyMeasurementMetricDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: float | None
    end: float | None
    delta: float | None


class CycleBodyMeasurementComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["complete", "missing_start", "missing_end", "missing_both"]
    start_measurement_id: UUID | None
    end_measurement_id: UUID | None
    start_measured_at: datetime | None
    end_measured_at: datetime | None
    metrics: dict[str, BodyMeasurementMetricDelta]


class CycleBodyAnalysisComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["complete", "missing_start", "missing_end", "missing_both"]
    start_session_id: UUID | None
    end_session_id: UUID | None
    start_analysis_id: UUID | None
    end_analysis_id: UUID | None
    start_result_version_id: UUID | None
    end_result_version_id: UUID | None
    start_created_at: datetime | None
    end_created_at: datetime | None
    comparison: NormalizedBodyProgressComparison | None
    improved_areas: list[BodyArea]
    unchanged_areas: list[BodyArea]
    lagging_areas: list[BodyArea]


class CycleBodyProgressProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cycle_id: UUID
    cycle_started_at: datetime
    cycle_completed_at: datetime | None


class CycleBodyProgressComparisonResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    measurement: CycleBodyMeasurementComparison
    body_analysis: CycleBodyAnalysisComparison
    missing_data: list[
        Literal["start_measurement", "end_measurement", "start_analysis", "end_analysis"]
    ]
    provenance: CycleBodyProgressProvenance


class WorkoutCycleBodyProgressComparisonResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    cycle_id: UUID
    result: CycleBodyProgressComparisonResult
    created_at: datetime
    updated_at: datetime
