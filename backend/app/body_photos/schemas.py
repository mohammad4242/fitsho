from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from app.body_photos.enums import BodyPhotoPurpose, BodyPhotoSessionState, BodyPhotoView

Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-fA-F]{64}$")]


class BodyPhotoCropEvidenceInput(BaseModel):
    confidence: float = Field(ge=0.8, le=1.0)
    original_height: int = Field(gt=0)
    crop_top: int = Field(ge=0)
    crop_bottom: int = Field(gt=0)
    processed_sha256: Sha256Hex
    crop_evidence_sha256: Sha256Hex


class BodyPhotoSessionCreate(BaseModel):
    purpose: BodyPhotoPurpose


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
    client_crop_confidence: float
    client_crop_confirmed: bool
    server_geometry_checked: bool
    content_url: str
    created_at: datetime
    updated_at: datetime


class BodyPhotoSessionResponse(BaseModel):
    id: UUID
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
