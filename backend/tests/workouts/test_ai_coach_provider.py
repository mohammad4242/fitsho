import asyncio

from app.body_analysis.providers.models import (
    StructuredGenerationRequest,
    StructuredGenerationResponse,
)
from app.workouts.ai_coach_provider import (
    AiCoachProvider,
    AiCoachRecommendationRequest,
    OpenRouterAiCoachProvider,
)


class StubOpenRouterProvider:
    async def generate_structured_text(
        self, request: StructuredGenerationRequest
    ) -> StructuredGenerationResponse:
        payload = request.input_payload
        assert payload["candidate_programs"][0]["candidate_id"] == "template-a"
        assert "raw_photo" not in payload
        return StructuredGenerationResponse(
            payload={
                "selected_candidate_id": "template-a",
                "program_explanation_fa": "با زمان و سطح فعلی شما هماهنگ است.",
                "day_explanations": [{"day_number": 1, "explanation_fa": "فشار کنترل‌شده است."}],
            },
            model_id="openrouter/test-model",
            attempted_models=("openrouter/test-model",),
            provider_request_id="request-1",
            input_tokens=123,
            output_tokens=45,
        )


class RecordingCoachProvider:
    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        self.requests: list[StructuredGenerationRequest] = []

    async def generate_structured_text(
        self, request: StructuredGenerationRequest
    ) -> StructuredGenerationResponse:
        self.requests.append(request)
        return StructuredGenerationResponse(
            payload={
                "selected_candidate_id": "template-a",
                "program_explanation_fa": "انتخاب نمونه.",
                "day_explanations": [],
            },
            model_id=self.model_id,
            attempted_models=(self.model_id,),
        )


def test_openrouter_ai_coach_accepts_only_a_supplied_candidate_and_day() -> None:
    provider = OpenRouterAiCoachProvider(StubOpenRouterProvider())

    recommendation = asyncio.run(
        provider.recommend(
            AiCoachRecommendationRequest(
                profile={"training_days_per_week": 3, "experience_level": "beginner"},
                candidate_programs=(
                    {
                        "candidate_id": "template-a",
                        "days": [{"day_number": 1, "exercise_names_fa": ["شنا سوئدی"]}],
                    },
                ),
                primary_model="openrouter/test-model",
                fallback_models=(),
                temperature=0.2,
                max_output_tokens=512,
            )
        )
    )

    assert recommendation.selected_candidate_id == "template-a"
    assert recommendation.program_explanation_fa == "با زمان و سطح فعلی شما هماهنگ است."
    assert recommendation.day_explanations[0].day_number == 1
    assert recommendation.model_id == "openrouter/test-model"


def test_openrouter_name_is_a_transitional_alias() -> None:
    assert OpenRouterAiCoachProvider is AiCoachProvider


def test_workout_request_is_identical_when_only_execution_provider_changes() -> None:
    api_provider = RecordingCoachProvider("api-model")
    agent_provider = RecordingCoachProvider("agent-model")
    request = AiCoachRecommendationRequest(
        profile={
            "training_days_per_week": 3,
            "experience_level": "beginner",
            "goal": "build_muscle",
        },
        candidate_programs=(
            {
                "candidate_id": "template-a",
                "days": [{"day_number": 1, "exercise_names_fa": ["شنا سوئدی"]}],
            },
            {
                "candidate_id": "template-b",
                "days": [{"day_number": 1, "exercise_names_fa": ["اسکوات"]}],
            },
        ),
        primary_model="configured-model",
        fallback_models=("fallback-model",),
        temperature=0.3,
        max_output_tokens=777,
    )

    asyncio.run(AiCoachProvider(api_provider).recommend(request))
    asyncio.run(AiCoachProvider(agent_provider).recommend(request))

    assert len(api_provider.requests) == 1
    assert len(agent_provider.requests) == 1
    assert api_provider.requests[0].model_dump() == agent_provider.requests[0].model_dump()
    assert api_provider.requests[0].input_payload == {
        "profile": request.profile,
        "candidate_programs": list(request.candidate_programs),
    }
