from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NotificationDeviceTokenUpsertRequest(BaseModel):
    provider: Literal["fcm", "apns"] = "fcm"
    token: str = Field(min_length=1, max_length=4096)

    model_config = ConfigDict(extra="forbid")

    @field_validator("token")
    @classmethod
    def normalize_token(cls, value: str) -> str:
        token = value.strip()
        if not token:
            raise ValueError("Notification token must not be blank")
        return token


class NotificationDeviceResponse(BaseModel):
    id: UUID
    device_id: str
    platform: Literal["android", "ios"]
    app_version: str
    device_name: str | None
    has_active_token: bool
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime


class NotificationPreferencesUpdateRequest(BaseModel):
    enabled: bool
    approved_plans: bool
    required_reviews: bool
    body_analysis: bool
    cycle_reminders: bool
    physician_decisions: bool
    nutrition_updates: bool = True

    model_config = ConfigDict(extra="forbid")


class NotificationPreferencesResponse(BaseModel):
    enabled: bool
    approved_plans: bool
    required_reviews: bool
    body_analysis: bool
    cycle_reminders: bool
    physician_decisions: bool
    nutrition_updates: bool
    updated_at: datetime | None
