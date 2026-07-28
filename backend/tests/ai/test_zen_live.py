import asyncio
import os

import httpx
import pytest
from workouts.evaluation_fixtures import evaluation_fixtures

from app.ai.opencode_zen import OpenCodeZenWorkoutPlanProvider
from app.ai.schemas import WorkoutGenerationModelResponse
from app.config import Settings
from app.workouts.prompt_builder import build_workout_generation_model_request


@pytest.mark.skipif(
    os.getenv("ZEN_LIVE_TEST") != "true",
    reason="requires explicit ZEN_LIVE_TEST=true",
)
def test_zen_live_with_synthetic_profile() -> None:
    fixture = evaluation_fixtures()[0]
    request = build_workout_generation_model_request(
        fixture.profile,
        fixture.candidates,
        fixture.policy,
    )
    settings = Settings()

    async def generate() -> WorkoutGenerationModelResponse:
        async with httpx.AsyncClient(
            proxy=settings.opencode_zen_proxy_url,
            trust_env=False,
        ) as client:
            provider = OpenCodeZenWorkoutPlanProvider(
                client,
                api_key=settings.opencode_zen_api_key,
                base_url=settings.opencode_zen_base_url,
                model=settings.opencode_zen_model,
                timeout_seconds=settings.opencode_zen_timeout_seconds,
            )
            return await provider.generate_plan(request)

    response = asyncio.run(generate())
    selected_ids = {
        exercise.exercise_id for day in response.plan.days for exercise in day.exercises
    }

    assert len(response.plan.days) == fixture.profile.training_days_per_week
    assert selected_ids.issubset(set(fixture.candidates.ids))
