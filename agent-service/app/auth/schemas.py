from datetime import datetime
from enum import StrEnum
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..schemas import AgentName, AuthState


class AuthSessionStatus(StrEnum):
    STARTING = "starting"
    WAITING_FOR_USER = "waiting_for_user"
    WAITING_FOR_INPUT = "waiting_for_input"
    VERIFYING = "verifying"
    AUTHENTICATED = "authenticated"
    FAILED = "failed"
    CANCELED = "canceled"
    EXPIRED = "expired"


class AuthInputLabel(StrEnum):
    AUTHORIZATION_CODE = "authorization code"
    VERIFICATION_CODE = "verification code"
    DEVICE_CODE = "device code"


class AuthSafeErrorMessage(StrEnum):
    FAILED = "authentication failed"
    EXPIRED = "authentication expired"
    CANCELED = "authentication was canceled"
    UNAVAILABLE = "authentication is unavailable"
    INVALID_INPUT = "authentication input is invalid"
    IN_PROGRESS = "authentication is already in progress"
    NOT_FOUND = "authentication session was not found"


class AuthStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AgentName
    force_reauth: bool = False


class AuthActiveCancellationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AgentName
    canceled: bool


class AuthLogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AgentName


class AuthLogoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AgentName
    auth_state: AuthState


class AuthInputRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1, max_length=4096)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        if not value.isprintable() or not value.strip():
            raise ValueError("authentication input must be printable")
        return value


class AuthSessionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    agent: AgentName
    status: AuthSessionStatus
    verification_url: str | None = None
    user_code: str | None = Field(default=None, min_length=1, max_length=256)
    input_label: str | None = None
    expires_at: datetime
    safe_error_message: str | None = None

    @field_validator("verification_url")
    @classmethod
    def validate_verification_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.isprintable():
            raise ValueError("verification URL must be printable")
        try:
            parsed = urlsplit(value)
            hostname = parsed.hostname
            port = parsed.port
        except ValueError as exc:
            raise ValueError("verification URL is invalid") from exc
        if (
            parsed.scheme.lower() != "https"
            or hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or (port is not None and not 1 <= port <= 65535)
        ):
            raise ValueError("verification URL must be an HTTPS URL without credentials")
        return value

    @field_validator("user_code")
    @classmethod
    def validate_user_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.isprintable() or not value.strip():
            raise ValueError("user code must be printable")
        return value

    @field_validator("input_label")
    @classmethod
    def validate_input_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in {label.value for label in AuthInputLabel}:
            raise ValueError("input label is not supported")
        return value

    @field_validator("safe_error_message")
    @classmethod
    def validate_safe_error_message(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in {message.value for message in AuthSafeErrorMessage}:
            raise ValueError("safe error message is not supported")
        return value
