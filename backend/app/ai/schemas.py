from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WorkoutPlanExerciseOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_id: UUID
    sets: int
    reps_min: int
    reps_max: int
    rest_seconds: int
    rir: int
    estimated_minutes: int
    notes_en: str | None
    notes_fa: str | None


class WorkoutPlanDayOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_number: int
    title_en: str
    title_fa: str
    estimated_duration_minutes: int
    exercises: list[WorkoutPlanExerciseOutput]


class WorkoutPlanModelOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    days: list[WorkoutPlanDayOutput]


@dataclass(frozen=True)
class WorkoutGenerationModelRequest:
    system_prompt: str
    input_payload: dict[str, object]
    response_schema: dict[str, object]


@dataclass(frozen=True)
class WorkoutGenerationModelResponse:
    plan: WorkoutPlanModelOutput
    provider_request_id: str | None
    input_tokens: int | None
    output_tokens: int | None


class ProviderErrorCode(StrEnum):
    NOT_CONFIGURED = "not_configured"
    TIMEOUT = "timeout"
    CONNECTION_FAILURE = "connection_failure"
    UNAUTHORIZED = "unauthorized"
    RATE_LIMITED = "rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    MALFORMED_RESPONSE = "malformed_response"
    INVALID_OUTPUT = "invalid_output"
    REFUSAL = "refusal"


class WorkoutProviderError(Exception):
    def __init__(
        self,
        code: ProviderErrorCode,
        safe_message: str,
        *,
        provider_status_code: int | None = None,
        provider_error_type: str | None = None,
        provider_error_message: str | None = None,
    ) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
        self.provider_status_code = provider_status_code
        self.provider_error_type = provider_error_type
        self.provider_error_message = provider_error_message
