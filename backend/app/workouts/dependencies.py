from typing import Annotated

import httpx
from fastapi import Depends, Request

from app.ai.opencode_zen import OpenCodeZenWorkoutPlanProvider
from app.ai.provider import WorkoutPlanModelProvider
from app.auth.dependencies import DatabaseSession
from app.config import Settings, get_settings
from app.workouts.service import WorkoutGenerationService, WorkoutGenerationSettings


def get_workout_plan_model_provider(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> WorkoutPlanModelProvider:
    client = request.app.state.http_client
    if not isinstance(client, httpx.AsyncClient):
        raise RuntimeError("Workout HTTP client is unavailable")
    return OpenCodeZenWorkoutPlanProvider(
        client,
        api_key=settings.opencode_zen_api_key,
        base_url=settings.opencode_zen_base_url,
        model=settings.opencode_zen_model,
        timeout_seconds=settings.opencode_zen_timeout_seconds,
    )


def get_workout_generation_service(
    db: DatabaseSession,
    provider: Annotated[WorkoutPlanModelProvider, Depends(get_workout_plan_model_provider)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WorkoutGenerationService:
    return WorkoutGenerationService(
        db,
        provider=provider,
        settings=WorkoutGenerationSettings(
            provider_name="opencode_zen",
            model_id=settings.opencode_zen_model,
            prompt_version=settings.workout_prompt_version,
            generation_policy_version=settings.workout_policy_version,
            catalog_programming_version=settings.workout_catalog_programming_version,
            max_repair_attempts=settings.workout_max_repair_attempts,
            cooldown_seconds=settings.workout_generation_cooldown_seconds,
            max_candidates=settings.workout_max_candidates,
            max_request_bytes=settings.workout_max_request_bytes,
            warmup_minutes=settings.workout_warmup_minutes,
        ),
    )


WorkoutGenerationServiceDependency = Annotated[
    WorkoutGenerationService,
    Depends(get_workout_generation_service),
]
