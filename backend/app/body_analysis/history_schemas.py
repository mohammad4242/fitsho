from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.body_analysis.api_schemas import (
    BodyAnalysisInputSnapshotResponse,
    BodyAnalysisResponse,
    SpecialistReviewState,
)
from app.body_analysis.comparison_schemas import BodyProgressComparisonResponse
from app.body_photos.enums import BodyPhotoPurpose, BodyPhotoSessionState
from app.body_photos.schemas import BodyPhotoResponse


class BodyProgressTimelineSession(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    cycle_id: UUID | None
    purpose: BodyPhotoPurpose
    state: BodyPhotoSessionState
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class BodyProgressTimelineReviewState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    coach: SpecialistReviewState
    doctor: SpecialistReviewState
    fully_reviewed: bool


class BodyProgressTimelineComparison(BodyProgressComparisonResponse):
    model_config = ConfigDict(extra="forbid", frozen=True)

    previous_session_date: datetime
    current_session_date: datetime
    interval_days: int
    before_photos: tuple[BodyPhotoResponse, ...]
    after_photos: tuple[BodyPhotoResponse, ...]


class BodyProgressTimelineItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    session: BodyProgressTimelineSession
    photos: tuple[BodyPhotoResponse, ...]
    analysis: BodyAnalysisResponse | None
    snapshot: BodyAnalysisInputSnapshotResponse | None
    comparison: BodyProgressTimelineComparison | None
    review_state: BodyProgressTimelineReviewState


class BodyProgressTimelineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    items: list[BodyProgressTimelineItem]
