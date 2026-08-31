from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints, model_validator

from app.body_analysis.admin_config.enums import (
    AIAgentName,
    AIExecutionBackend,
    AIProviderName,
    AIRoutingPolicy,
    AITaskType,
)


class CredentialStatus(BaseModel):
    configured: bool
    masked: str | None


AgentModelId = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)
]


class AITaskConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: AIProviderName = AIProviderName.OPENROUTER
    execution_backend: AIExecutionBackend = AIExecutionBackend.API
    agent_name: AIAgentName | None = None
    agent_model_id: AgentModelId | None = None
    enabled: bool = False
    api_key: SecretStr | None = Field(default=None, repr=False)
    replace_credential: bool = False
    primary_model_id: str | None = Field(default=None, min_length=1, max_length=300)
    fallback_model_ids: list[Annotated[str, Field(min_length=1, max_length=300)]] = Field(
        default_factory=list,
        max_length=5,
    )
    temperature: float = Field(default=0.0, ge=0, le=2)
    max_output_tokens: int = Field(default=4096, ge=1, le=65_536)
    timeout_seconds: int = Field(default=45, ge=1, le=180)
    minimum_confidence: float = Field(default=0.7, ge=0, le=1)
    max_cost_per_request: Decimal | None = Field(default=None, ge=0)
    routing_restrictions: list[AIRoutingPolicy] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def credential_replacement_is_explicit(self) -> "AITaskConfigUpdate":
        if self.api_key is not None and not self.replace_credential:
            raise ValueError("Credential replacement must be explicit")
        if self.replace_credential and self.api_key is None:
            raise ValueError("A replacement API key is required")
        if len(set(self.fallback_model_ids)) != len(self.fallback_model_ids):
            raise ValueError("Fallback models must be unique")
        if self.primary_model_id in self.fallback_model_ids:
            raise ValueError("Primary model cannot also be a fallback")
        if len(set(self.routing_restrictions)) != len(self.routing_restrictions):
            raise ValueError("Routing policies must be unique")
        return self


class AITaskConfigDetail(BaseModel):
    task_type: AITaskType
    provider: AIProviderName
    execution_backend: AIExecutionBackend
    agent_name: AIAgentName | None
    agent_model_id: str | None
    enabled: bool
    primary_model_id: str | None
    fallback_model_ids: list[str]
    temperature: float
    max_output_tokens: int
    timeout_seconds: int
    minimum_confidence: float
    max_cost_per_request: Decimal | None
    routing_restrictions: list[AIRoutingPolicy]
    credential: CredentialStatus
    last_successful_connection_test_at: datetime | None
    last_model_catalog_refresh_at: datetime | None
    last_error_code: str | None
    last_error_message: str | None


class ProviderDetail(BaseModel):
    provider: AIProviderName
    display_name: str
    credential: CredentialStatus


class ProviderTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: AIProviderName = AIProviderName.OPENROUTER
    api_key: SecretStr | None = Field(default=None, repr=False)


class ProviderTestResponse(BaseModel):
    ok: bool
    checked_at: datetime
    model_count: int | None = None
    error_code: str | None = None
    safe_error_message: str | None = None


class ModelCatalogItem(BaseModel):
    provider: AIProviderName
    model_id: str
    display_name: str
    provider_family: str
    supports_text_input: bool
    supports_image_input: bool
    supports_structured_output: bool
    context_length: int | None
    input_price_per_token: Decimal | None
    output_price_per_token: Decimal | None
    available: bool


class ModelCatalogResponse(BaseModel):
    items: list[ModelCatalogItem]
    refreshed_at: datetime | None
    stale: bool


class ModelCatalogRefreshResponse(BaseModel):
    provider: AIProviderName
    model_count: int
    refreshed_at: datetime
