from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.body_photos.enums import BodyPhotoPurpose, BodyPhotoSessionState, BodyPhotoView


class BodyPhotoSessionCreate(BaseModel):
    purpose: BodyPhotoPurpose
    cycle_id: UUID | None = None


class BodyPhotoConsentInput(BaseModel):
    granted: bool
    version: str = Field(min_length=1, max_length=64)


class BodyPhotoSubmit(BaseModel):
    operational_processing: BodyPhotoConsentInput
    model_training: BodyPhotoConsentInput = Field(
        default_factory=lambda: BodyPhotoConsentInput(
            granted=False,
            version="model-training-v1",
        )
    )


class BodyPhotoConsentResponse(BaseModel):
    granted: bool
    version: str
    recorded_at: datetime


class BodyPhotoResponse(BaseModel):
    id: UUID
    view: BodyPhotoView
    mime_type: str
    byte_size: int
    width: int
    height: int
    content_url: str
    created_at: datetime
    updated_at: datetime


class BodyPhotoSessionResponse(BaseModel):
    id: UUID
    cycle_id: UUID | None
    purpose: BodyPhotoPurpose
    state: BodyPhotoSessionState
    photos: list[BodyPhotoResponse]
    operational_processing_consent: BodyPhotoConsentResponse | None
    model_training_consent: BodyPhotoConsentResponse | None
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class BodyPhotoSessionListResponse(BaseModel):
    items: list[BodyPhotoSessionResponse]
