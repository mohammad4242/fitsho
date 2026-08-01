from typing import Annotated

import httpx
from fastapi import Depends, Request

from app.ai.catalog import NoEnabledRouteModelsError, select_route_models
from app.ai.routing import ModelProviderCandidate, build_model_candidates
from app.auth.dependencies import DatabaseSession
from app.auth.models import User
from app.config import Settings, get_settings
from app.exercises.dependencies import require_completed_profile
from app.profile.enums import WorkoutGenerationMethod
from app.profile.service import get_profile
from app.workouts.service import WorkoutGenerationService, WorkoutGenerationSettings


def get_workout_generation_service(
    db: DatabaseSession,
    request: Request,
    user: Annotated[User, Depends(require_completed_profile)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WorkoutGenerationService:
    method = get_profile(db, user.id).profile.workout_generation_method
    providers: tuple[ModelProviderCandidate, ...] = ()
    provider_name = "fitsho_domain"
    model_id = "program_engine_v1"
    prompt_version = "none"
    generation_policy_version = "resistance_training_v1"
    if method is WorkoutGenerationMethod.AI:
        client = request.app.state.zen_http_client
        if not isinstance(client, httpx.AsyncClient):
            raise RuntimeError("Workout HTTP client is unavailable")
        try:
            models = select_route_models(db)
        except NoEnabledRouteModelsError as error:
            raise RuntimeError("No enabled workout model is configured") from error
        providers = build_model_candidates(
            models,
            client,
            api_key=settings.opencode_zen_api_key,
            base_url=settings.opencode_zen_base_url,
            timeout_seconds=settings.opencode_zen_timeout_seconds,
        )
        provider_name = "opencode_zen"
        model_id = providers[0].model_id
        prompt_version = settings.workout_prompt_version
        generation_policy_version = settings.workout_policy_version
    return WorkoutGenerationService(
        db,
        providers=providers,
        settings=WorkoutGenerationSettings(
            provider_name=provider_name,
            model_id=model_id,
            prompt_version=prompt_version,
            generation_policy_version=generation_policy_version,
            catalog_programming_version=settings.workout_catalog_programming_version,
            max_repair_attempts=0,
            cooldown_seconds=settings.workout_generation_cooldown_seconds,
            max_candidates=settings.workout_max_candidates,
            max_request_bytes=settings.workout_max_request_bytes,
            warmup_minutes=settings.workout_warmup_minutes,
            deterministic_fallback_enabled=False,
            generation_method=method.value,
        ),
    )


WorkoutGenerationServiceDependency = Annotated[
    WorkoutGenerationService,
    Depends(get_workout_generation_service),
]
