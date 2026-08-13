from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.auth.security import normalize_iranian_phone


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    model_config = ConfigDict(extra="forbid")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    model_config = ConfigDict(extra="forbid")


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    model_config = ConfigDict(extra="forbid")


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=8, max_length=128)

    model_config = ConfigDict(extra="forbid")


class GenericMessageResponse(BaseModel):
    message: str


class PhoneSendOtpRequest(BaseModel):
    phone_number: str = Field(min_length=11, max_length=14)

    model_config = ConfigDict(extra="forbid")

    @field_validator("phone_number")
    @classmethod
    def normalize_phone_number(cls, value: str) -> str:
        return normalize_iranian_phone(value)


class PhoneVerifyOtpRequest(PhoneSendOtpRequest):
    code: str = Field(pattern=r"^\d{6}$")


class PhoneOtpSentResponse(BaseModel):
    message: str
    retry_after_seconds: int


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr | None
    phone_number: str | None
    created_at: datetime
    is_admin: bool

    model_config = ConfigDict(from_attributes=True)
