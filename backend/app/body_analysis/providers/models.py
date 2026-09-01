from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProviderErrorCode(StrEnum):
    NOT_CONFIGURED = "not_configured"
    TIMEOUT = "timeout"
    CONNECTION_FAILURE = "connection_failure"
    UNAUTHORIZED = "unauthorized"
    RATE_LIMITED = "rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    INVALID_REQUEST = "invalid_request"
    MALFORMED_RESPONSE = "malformed_response"
    INVALID_OUTPUT = "invalid_output"
    REFUSAL = "refusal"
    MODEL_NOT_FOUND = "model_not_found"


class AIProviderError(Exception):
    def __init__(
        self,
        code: ProviderErrorCode,
        safe_message: str,
        *,
        provider_status_code: int | None = None,
        provider_request_id: str | None = None,
    ) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
        self.provider_status_code = provider_status_code
        self.provider_request_id = provider_request_id


class ModelCapabilityFilter(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text_input: bool | None = None
    image_input: bool | None = None
    structured_output: bool | None = None


class ModelCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    model_id: str
    display_name: str
    provider_family: str
    supports_text_input: bool
    supports_image_input: bool
    supports_structured_output: bool
    context_length: int | None
    input_price_per_token: Decimal | None
    output_price_per_token: Decimal | None
    available: bool = True

    def matches(self, filters: ModelCapabilityFilter) -> bool:
        expected = (
            (filters.text_input, self.supports_text_input),
            (filters.image_input, self.supports_image_input),
            (filters.structured_output, self.supports_structured_output),
        )
        return all(required is None or required is actual for required, actual in expected)


class ModelRoute(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    primary_model: str = Field(min_length=1, max_length=300)
    fallback_models: tuple[str, ...] = Field(default=(), max_length=5)


class ProviderRoutingPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    data_collection: Literal["deny"] | None = None
    zdr: bool | None = None
    require_parameters: bool | None = None


class ImageInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(min_length=1, max_length=40)
    mime_type: Literal["image/jpeg", "image/png", "image/webp"]
    base64_data: str | None = Field(default=None, min_length=1, repr=False)
    storage_scope: Literal["body", "food"] | None = None
    storage_key: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_source(self) -> ImageInput:
        has_inline = self.base64_data is not None
        has_scope = self.storage_scope is not None
        has_key = self.storage_key is not None
        if has_inline and not (not has_scope and not has_key):
            raise ValueError("image source must be inline or stored, not both")
        if not has_inline and not (has_scope and has_key):
            raise ValueError("stored image source requires scope and key")
        if has_scope != has_key:
            raise ValueError("stored image source requires scope and key")
        return self


class StructuredGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    system_prompt: str = Field(min_length=1, max_length=50_000)
    input_payload: dict[str, Any]
    response_schema: dict[str, Any]
    schema_name: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    route: ModelRoute
    provider_preferences: ProviderRoutingPreferences = Field(
        default_factory=ProviderRoutingPreferences
    )
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=4096, ge=1, le=65_536)


class StructuredGenerationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    payload: dict[str, Any]
    model_id: str
    attempted_models: tuple[str, ...]
    provider_request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost: Decimal | None = None


class ProviderConnectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: Literal[True] = True
    checked_at: datetime
    model_count: int


@dataclass(frozen=True)
class _ProviderCompletion:
    payload: dict[str, Any]
    provider_request_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    cost: Decimal | None
