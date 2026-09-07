from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AccountDeletionInitiateRequest(BaseModel):
    confirmation: Literal["DELETE"]
    password: str | None = Field(default=None, min_length=8, max_length=128)

    model_config = ConfigDict(extra="forbid")


class AccountDeletionCancelRequest(BaseModel):
    confirmation: Literal["CANCEL"]

    model_config = ConfigDict(extra="forbid")


class AccountDeletionStatusResponse(BaseModel):
    status: Literal["none", "pending", "cancelled", "completed"]
    request_id: UUID | None
    requested_at: datetime | None
    reauthenticated_at: datetime | None
    grace_period_ends_at: datetime | None
    cancelled_at: datetime | None
    completed_at: datetime | None
