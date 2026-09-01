from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ModelId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=300),
]


class AgentName(StrEnum):
    ANTIGRAVITY = "antigravity"
    CODEX = "codex"
    CLAUDE = "claude"


class AgentTaskKind(StrEnum):
    WORKOUT_PLAN_GENERATION = "workout_plan_generation"
    BODY_PHOTO_ANALYSIS = "body_photo_analysis"
    FOOD_PHOTO_ESTIMATION = "food_photo_estimation"
    FOOD_PRICE_SEARCH = "food_price_search"


class ReasoningEffort(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    THINKING = "thinking"


class AgentModelProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{1,180}$")
    agent: AgentName
    display_name: str = Field(min_length=1, max_length=300)
    model_id: str = Field(min_length=1, max_length=300)
    effort: ReasoningEffort | None = None
    task_kinds: tuple[AgentTaskKind, ...] = Field(min_length=1, max_length=4)
    fingerprint: str = Field(pattern=r"^[a-f0-9]{16,64}$")
    supports_text_input: bool = True
    supports_image_input: bool = False
    supports_structured_output: bool = True


class AgentGenerationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AgentName
    model_id: ModelId
    profile_id: str | None = Field(default=None, min_length=1, max_length=200)
    system_prompt: Annotated[NonBlankText, StringConstraints(max_length=50_000)]
    input_payload: dict[str, Any]
    response_schema: dict[str, Any]
    schema_name: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    temperature: float = Field(ge=0, le=2)
    max_output_tokens: int = Field(ge=1, le=65_536)
    timeout_seconds: float = Field(gt=0, le=600)
    # Multipart transport metadata. Backend task semantics remain in the fields above.
    image_labels: tuple[
        Annotated[str, StringConstraints(min_length=1, max_length=40)], ...
    ] | None = Field(
        default=None,
        max_length=5,
    )


class AgentGenerationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payload: dict[str, Any]
    agent: AgentName
    model_id: ModelId
    profile_id: str | None = Field(default=None, exclude_if=lambda value: value is None)
    request_id: NonBlankText
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    duration_seconds: float = Field(ge=0)


class AuthState(StrEnum):
    UNKNOWN = "unknown"
    AUTHENTICATED = "authenticated"
    UNAUTHENTICATED = "unauthenticated"


class AuthMode(StrEnum):
    UNKNOWN = "unknown"
    BROWSER_LINK = "browser_link"
    MANUAL = "manual"


class RunnerModelCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: ModelId
    supports_text_input: bool
    supports_image_input: bool
    supports_structured_output: bool
    supports_temperature: bool = False
    supports_max_output_tokens: bool = False


class RunnerCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AgentName
    installed: bool
    version: str | None = None
    auth_state: AuthState = AuthState.UNKNOWN
    auth_mode: AuthMode = AuthMode.UNKNOWN
    models: list[RunnerModelCapabilities] = Field(default_factory=list)
    profiles: list[AgentModelProfile] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class CapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runners: list[RunnerCapabilities]


class TestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: AgentName
    model_id: ModelId | None = None
    profile_id: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def require_model_or_profile(self) -> "TestRequest":
        if self.model_id is None and self.profile_id is None:
            raise ValueError("model_id or profile_id is required")
        return self


class TestOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    agent: AgentName
    model_id: ModelId
    profile_id: str | None = Field(default=None, exclude_if=lambda value: value is None)
    request_id: NonBlankText
    duration_seconds: float = Field(ge=0)


class ErrorCode(StrEnum):
    TIMEOUT = "timeout"
    UNAUTHORIZED = "unauthorized"
    RATE_LIMITED = "rate_limited"
    INVALID_REQUEST = "invalid_request"
    INVALID_OUTPUT = "invalid_output"
    MODEL_NOT_FOUND = "model_not_found"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    AUTH_IN_PROGRESS = "auth_in_progress"
    AUTH_SESSION_NOT_FOUND = "auth_session_not_found"
    AUTH_SESSION_EXPIRED = "auth_session_expired"
    AUTH_INPUT_NOT_EXPECTED = "auth_input_not_expected"
    AUTH_INPUT_INVALID = "auth_input_invalid"
    AUTH_UNAVAILABLE = "auth_unavailable"
    AUTH_MANUAL_ONLY = "auth_manual_only"


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: ErrorCode
    message: NonBlankText
    request_id: NonBlankText


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorDetail
