from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.body_analysis.admin_config.enums import (
    AIAgentName,
    AIAgentServiceProxySource,
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
    agent_profile_id: AgentModelId | None = None
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
    agent_profile_id: str | None
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


class AgentServiceModelCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: AgentModelId
    supports_text_input: bool
    supports_image_input: bool
    supports_structured_output: bool
    supports_live_web: bool = False
    # Agent Service exposes these runner-parameter flags for future UI support.
    # Backend v1 accepts them at the boundary but deliberately keeps them out of
    # the public admin contract until each runner is verified and wired.
    supports_temperature: bool = Field(default=False, exclude=True)
    supports_max_output_tokens: bool = Field(default=False, exclude=True)


class AgentServiceRunnerCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AIAgentName
    installed: bool
    version: str | None = Field(default=None, max_length=120)
    auth_state: Literal["unknown", "authenticated", "unauthenticated"] = "unknown"
    auth_mode: Literal["unknown", "browser_link", "manual"] = "unknown"
    models: list[AgentServiceModelCapability] = Field(default_factory=list)
    profiles: list["AgentServiceModelProfile"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class AgentServiceModelProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: AgentModelId
    agent: AIAgentName
    display_name: str = Field(min_length=1, max_length=300)
    model_id: AgentModelId
    effort: Literal["low", "medium", "high", "thinking"] | None = None
    task_kinds: list[AITaskType] = Field(min_length=1, max_length=4)
    fingerprint: str = Field(pattern=r"^[a-f0-9]{16,64}$")
    supports_text_input: bool
    supports_image_input: bool
    supports_structured_output: bool
    supports_live_web: bool = False
    verification_status: Literal["unverified", "passed", "failed", "stale"] = "unverified"
    verified_at: datetime | None = None
    verification_error_code: str | None = None
    verification_safe_error_message: str | None = None


class AgentServiceProfileVerification(BaseModel):
    profile_id: AgentModelId
    task_type: AITaskType
    fingerprint: str
    status: Literal["unverified", "passed", "failed", "stale"]
    checked_at: datetime | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    error_code: str | None = None
    safe_error_message: str | None = None


class AgentServiceProfileSummary(AgentServiceModelProfile):
    verification: list[AgentServiceProfileVerification] = Field(default_factory=list)


class AgentServiceCapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runners: list[AgentServiceRunnerCapability]


class AgentServiceTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AIAgentName
    model_id: AgentModelId
    profile_id: AgentModelId | None = None


class AgentServiceTestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    agent: AIAgentName
    model_id: AgentModelId
    profile_id: AgentModelId | None = None
    checked_at: datetime
    duration_seconds: float | None = Field(default=None, ge=0)
    error_code: str | None = None
    safe_error_message: str | None = None


class AgentServiceTaskSmokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_type: AITaskType
    agent: AIAgentName
    profile_id: AgentModelId


class AgentServiceTaskSmokeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    task_type: AITaskType
    agent: AIAgentName
    profile_id: AgentModelId
    fingerprint: str | None = None
    stage: Literal[
        "backend_request",
        "agent_service",
        "runner",
        "schema",
        "semantic_validation",
        "passed",
        "failed",
    ]
    request_id: str | None = None
    checked_at: datetime
    duration_seconds: float | None = Field(default=None, ge=0)
    error_code: str | None = None
    safe_error_message: str | None = None


class AgentServiceProxyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    source: AIAgentServiceProxySource = AIAgentServiceProxySource.DEPLOYMENT_DEFAULT
    proxy_url: SecretStr | None = Field(default=None, max_length=500, repr=False)

    @field_validator("proxy_url")
    @classmethod
    def validate_proxy_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        candidate = value.get_secret_value().strip()
        if not candidate or any(character.isspace() for character in candidate):
            raise ValueError("Proxy URL must be a non-empty URL")
        try:
            parsed = urlsplit(candidate)
            hostname = parsed.hostname
            port = parsed.port
        except ValueError as error:
            raise ValueError("Proxy URL is invalid") from error
        if (
            parsed.scheme.lower() not in {"http", "https", "socks5", "socks5h"}
            or not hostname
            or (port is not None and not 1 <= port <= 65_535)
        ):
            raise ValueError("Proxy URL must use a supported proxy scheme")
        return SecretStr(candidate)

    @model_validator(mode="after")
    def validate_source_url_pair(self) -> "AgentServiceProxyUpdate":
        if (
            self.source is AIAgentServiceProxySource.DEPLOYMENT_DEFAULT
            and self.proxy_url is not None
        ):
            raise ValueError("Deployment default cannot include a custom proxy URL")
        if (
            self.source is AIAgentServiceProxySource.CUSTOM
            and self.enabled
            and self.proxy_url is None
        ):
            raise ValueError("A custom proxy URL is required when proxy is enabled")
        return self


class AgentServiceProxyRuntimeStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    source: AIAgentServiceProxySource
    configured: bool
    default_configured: bool
    masked_proxy_url: str | None = None


class AgentServiceProxyDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    source: AIAgentServiceProxySource
    configured: bool
    default_configured: bool
    masked_proxy_url: str | None = None
    applied: bool
    agent_service_available: bool
    last_applied_at: datetime | None = None
    last_apply_error: str | None = None


AgentAuthStatus = Literal[
    "starting",
    "waiting_for_user",
    "waiting_for_input",
    "verifying",
    "authenticated",
    "failed",
    "canceled",
    "expired",
]
AgentAuthInputLabel = Literal["authorization code", "verification code", "device code"]
AgentAuthSafeErrorMessage = Literal[
    "authentication failed",
    "authentication expired",
    "authentication was canceled",
    "authentication is unavailable",
    "authentication input is invalid",
    "authentication is already in progress",
    "authentication session was not found",
]

_AGENT_AUTH_HOSTS = {
    AIAgentName.ANTIGRAVITY: "accounts.google.com",
    AIAgentName.CODEX: "auth.openai.com",
    AIAgentName.CLAUDE: "claude.com",
}


class AgentServiceAuthStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AIAgentName
    force_reauth: bool = False


class AgentServiceAuthActiveCancellationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AIAgentName
    canceled: bool


class AgentServiceAuthLogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AIAgentName


class AgentServiceAuthLogoutResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AIAgentName
    auth_state: Literal["unauthenticated"]


class AgentServiceAuthInputRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1, max_length=4096, repr=False)

    @field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        if not value.isprintable() or not value.strip():
            raise ValueError("Authentication input must be printable")
        return value


class AgentServiceAuthSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    agent: AIAgentName
    status: AgentAuthStatus
    verification_url: str | None = Field(default=None, max_length=4096)
    user_code: str | None = Field(default=None, min_length=1, max_length=256)
    input_label: AgentAuthInputLabel | None = None
    expires_at: datetime
    safe_error_message: AgentAuthSafeErrorMessage | None = None

    @field_validator("verification_url")
    @classmethod
    def validate_verification_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.isprintable():
            raise ValueError("Verification URL must be printable")
        try:
            parsed = urlsplit(value)
            hostname = parsed.hostname
            port = parsed.port
        except ValueError as error:
            raise ValueError("Verification URL is invalid") from error
        if (
            parsed.scheme.lower() != "https"
            or hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or (port is not None and not 1 <= port <= 65535)
        ):
            raise ValueError("Verification URL must be an HTTPS URL without credentials")
        return value

    @field_validator("user_code")
    @classmethod
    def validate_user_code(cls, value: str | None) -> str | None:
        if value is not None and (not value.isprintable() or not value.strip()):
            raise ValueError("User code must be printable")
        return value

    @model_validator(mode="after")
    def validate_agent_auth_host(self) -> "AgentServiceAuthSessionResponse":
        if self.verification_url is None:
            return self
        try:
            hostname = urlsplit(self.verification_url).hostname
        except ValueError as error:
            raise ValueError("Verification URL is invalid") from error
        expected_host = _AGENT_AUTH_HOSTS.get(self.agent)
        if expected_host is None or hostname is None or hostname.lower() != expected_host:
            raise ValueError("Verification URL host is not approved")
        return self
