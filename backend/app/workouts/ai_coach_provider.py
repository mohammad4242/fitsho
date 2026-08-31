from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.ai.schemas import ProviderErrorCode, WorkoutProviderError
from app.body_analysis.providers.models import (
    AIProviderError,
    ModelRoute,
    ProviderRoutingPreferences,
    StructuredGenerationRequest,
    StructuredGenerationResponse,
)
from app.body_analysis.providers.models import ProviderErrorCode as OpenRouterErrorCode


class StructuredTextProvider(Protocol):
    async def generate_structured_text(
        self, request: StructuredGenerationRequest
    ) -> StructuredGenerationResponse: ...


class AiCoachDayExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    day_number: int = Field(ge=1, le=7)
    explanation_fa: str = Field(min_length=1, max_length=1_200)


class AiCoachRecommendationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    selected_candidate_id: str = Field(min_length=1, max_length=160)
    program_explanation_fa: str = Field(min_length=1, max_length=2_000)
    day_explanations: tuple[AiCoachDayExplanation, ...] = Field(default=(), max_length=7)


@dataclass(frozen=True)
class AiCoachRecommendationRequest:
    profile: dict[str, object]
    candidate_programs: tuple[dict[str, object], ...]
    primary_model: str
    fallback_models: tuple[str, ...]
    temperature: float
    max_output_tokens: int
    routing_preferences: ProviderRoutingPreferences = ProviderRoutingPreferences()


@dataclass(frozen=True)
class AiCoachRecommendation:
    selected_candidate_id: str
    program_explanation_fa: str
    day_explanations: tuple[AiCoachDayExplanation, ...]
    model_id: str
    provider_request_id: str | None
    input_tokens: int | None
    output_tokens: int | None


class AiCoachProvider:
    def __init__(self, provider: StructuredTextProvider) -> None:
        self._provider = provider

    async def recommend(self, request: AiCoachRecommendationRequest) -> AiCoachRecommendation:
        candidate_ids = {
            candidate["candidate_id"]
            for candidate in request.candidate_programs
            if isinstance(candidate.get("candidate_id"), str)
        }
        day_numbers: set[int] = set()
        for candidate in request.candidate_programs:
            days = candidate.get("days")
            if not isinstance(days, list):
                continue
            for day in days:
                if isinstance(day, dict) and isinstance(day.get("day_number"), int):
                    day_numbers.add(day["day_number"])
        try:
            response = await self._provider.generate_structured_text(
                StructuredGenerationRequest(
                    system_prompt=(
                        "You are Fitsho AI Coach. Select exactly one supplied candidate program. "
                        "Do not modify exercises, prescriptions, or safety constraints. "
                        "Explain the selection in clear Persian. Add a Persian day explanation "
                        "only when it provides useful user-specific context."
                    ),
                    input_payload={
                        "profile": request.profile,
                        "candidate_programs": list(request.candidate_programs),
                    },
                    response_schema=AiCoachRecommendationPayload.model_json_schema(),
                    schema_name="fitsho_ai_coach_recommendation",
                    route=ModelRoute(
                        primary_model=request.primary_model,
                        fallback_models=request.fallback_models,
                    ),
                    provider_preferences=request.routing_preferences,
                    temperature=request.temperature,
                    max_output_tokens=request.max_output_tokens,
                )
            )
            payload = AiCoachRecommendationPayload.model_validate(response.payload)
        except AIProviderError as error:
            raise _workout_provider_error(error) from None
        except ValidationError as error:
            raise WorkoutProviderError(
                ProviderErrorCode.INVALID_OUTPUT,
                "The AI coach returned invalid structured output.",
            ) from error
        if payload.selected_candidate_id not in candidate_ids:
            raise WorkoutProviderError(
                ProviderErrorCode.INVALID_OUTPUT,
                "The AI coach selected an unavailable workout program.",
            )
        if any(item.day_number not in day_numbers for item in payload.day_explanations):
            raise WorkoutProviderError(
                ProviderErrorCode.INVALID_OUTPUT,
                "The AI coach returned an explanation for an unavailable workout day.",
            )
        return AiCoachRecommendation(
            selected_candidate_id=payload.selected_candidate_id,
            program_explanation_fa=payload.program_explanation_fa,
            day_explanations=payload.day_explanations,
            model_id=response.model_id,
            provider_request_id=response.provider_request_id,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )


def _workout_provider_error(error: AIProviderError) -> WorkoutProviderError:
    codes = {
        OpenRouterErrorCode.NOT_CONFIGURED: ProviderErrorCode.NOT_CONFIGURED,
        OpenRouterErrorCode.TIMEOUT: ProviderErrorCode.TIMEOUT,
        OpenRouterErrorCode.CONNECTION_FAILURE: ProviderErrorCode.CONNECTION_FAILURE,
        OpenRouterErrorCode.UNAUTHORIZED: ProviderErrorCode.UNAUTHORIZED,
        OpenRouterErrorCode.RATE_LIMITED: ProviderErrorCode.RATE_LIMITED,
        OpenRouterErrorCode.PROVIDER_UNAVAILABLE: ProviderErrorCode.PROVIDER_UNAVAILABLE,
        OpenRouterErrorCode.MALFORMED_RESPONSE: ProviderErrorCode.MALFORMED_RESPONSE,
        OpenRouterErrorCode.REFUSAL: ProviderErrorCode.REFUSAL,
        OpenRouterErrorCode.INVALID_OUTPUT: ProviderErrorCode.INVALID_OUTPUT,
        # Workout APIs do not expose request/model configuration details.
        OpenRouterErrorCode.INVALID_REQUEST: ProviderErrorCode.PROVIDER_UNAVAILABLE,
        OpenRouterErrorCode.MODEL_NOT_FOUND: ProviderErrorCode.PROVIDER_UNAVAILABLE,
    }
    return WorkoutProviderError(
        codes.get(error.code, ProviderErrorCode.PROVIDER_UNAVAILABLE),
        error.safe_message,
        provider_status_code=error.provider_status_code,
    )


# Transitional name retained for existing workout dependencies and callers.
OpenRouterAiCoachProvider = AiCoachProvider
