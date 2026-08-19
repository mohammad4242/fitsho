from typing import Annotated

import httpx
from fastapi import Depends, Request
from sqlalchemy import select

from app.auth.dependencies import DatabaseSession
from app.auth.models import User
from app.body_analysis.admin_config.enums import AIRoutingPolicy, AITaskType
from app.body_analysis.admin_config.models import AITaskConfig
from app.body_analysis.admin_config.service import (
    AIConfigError,
    decrypted_key,
    openrouter_provider,
)
from app.body_analysis.providers import ProviderRoutingPreferences
from app.config import Settings, get_settings
from app.exercises.dependencies import require_completed_profile
from app.profile.enums import WorkoutGenerationMethod
from app.profile.service import get_profile
from app.workouts.ai_coach_provider import OpenRouterAiCoachProvider
from app.workouts.service import WorkoutGenerationService, WorkoutGenerationSettings


def get_workout_generation_service(
    db: DatabaseSession,
    request: Request,
    user: Annotated[User, Depends(require_completed_profile)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WorkoutGenerationService:
    method = get_profile(db, user.id).profile.workout_generation_method
    if method is None:
        raise RuntimeError("Completed fitness profile required")
    ai_coach_provider: OpenRouterAiCoachProvider | None = None
    provider_name = "fitsho_domain"
    model_id = "program_engine_v1"
    prompt_version = "none"
    generation_policy_version = "resistance_training_v1"
    ai_coach_fallback_models: tuple[str, ...] = ()
    ai_coach_temperature = 0.0
    ai_coach_max_output_tokens = 4096
    ai_coach_preferences = ProviderRoutingPreferences()
    if method is WorkoutGenerationMethod.AI:
        task = db.scalar(
            select(AITaskConfig).where(AITaskConfig.task_type == AITaskType.WORKOUT_PLAN_GENERATION)
        )
        if task is None or not task.enabled or not task.primary_model_id:
            raise RuntimeError("AI Coach is not configured")
        client = request.app.state.ai_http_client
        if not isinstance(client, httpx.AsyncClient):
            raise RuntimeError("Workout HTTP client is unavailable")
        try:
            key = decrypted_key(db, provider=task.provider, settings=settings)
            policies = tuple(AIRoutingPolicy(item) for item in task.routing_restrictions)
        except (AIConfigError, ValueError) as error:
            raise RuntimeError("AI Coach is not configured") from error
        ai_coach_provider = OpenRouterAiCoachProvider(
            openrouter_provider(
                client,
                api_key=key,
                settings=settings,
                timeout_seconds=task.timeout_seconds,
            )
        )
        provider_name = task.provider.value
        model_id = task.primary_model_id
        prompt_version = settings.workout_prompt_version
        generation_policy_version = settings.workout_policy_version
        ai_coach_fallback_models = tuple(task.fallback_model_ids)
        ai_coach_temperature = task.temperature
        ai_coach_max_output_tokens = task.max_output_tokens
        ai_coach_preferences = ProviderRoutingPreferences(
            data_collection=(
                "deny" if AIRoutingPolicy.DENY_PROVIDER_DATA_COLLECTION in policies else None
            ),
            zdr=True if AIRoutingPolicy.ZERO_DATA_RETENTION in policies else None,
            require_parameters=(
                True if AIRoutingPolicy.REQUIRE_SUPPORTED_PARAMETERS in policies else None
            ),
        )
    return WorkoutGenerationService(
        db,
        ai_coach_provider=ai_coach_provider,
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
            deterministic_fallback_enabled=settings.workout_deterministic_fallback_enabled,
            generation_method=method.value,
            ai_coach_fallback_models=ai_coach_fallback_models,
            ai_coach_temperature=ai_coach_temperature,
            ai_coach_max_output_tokens=ai_coach_max_output_tokens,
            ai_coach_routing_preferences=ai_coach_preferences,
        ),
    )


WorkoutGenerationServiceDependency = Annotated[
    WorkoutGenerationService,
    Depends(get_workout_generation_service),
]
