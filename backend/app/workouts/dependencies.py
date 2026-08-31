from typing import Annotated

import httpx
from fastapi import Depends, Request
from sqlalchemy import select

from app.ai.task_provider import build_task_provider
from app.auth.dependencies import DatabaseSession
from app.auth.models import User
from app.body_analysis.admin_config.enums import AIExecutionBackend, AITaskType
from app.body_analysis.admin_config.models import AITaskConfig
from app.body_analysis.admin_config.service import (
    AIConfigError,
    decrypted_key,
)
from app.body_analysis.providers import ProviderRoutingPreferences
from app.config import Settings, get_settings
from app.exercises.dependencies import require_completed_profile
from app.profile.enums import WorkoutGenerationMethod
from app.profile.service import get_profile
from app.workouts.ai_coach_provider import AiCoachProvider
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
    ai_coach_provider: AiCoachProvider | None = None
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
        if task is None or not task.enabled:
            raise RuntimeError("AI Coach is not configured")
        try:
            backend = AIExecutionBackend(task.execution_backend)
            client_name = (
                "ai_http_client" if backend is AIExecutionBackend.API else "agent_http_client"
            )
            client = getattr(request.app.state, client_name, None)
            if not isinstance(client, httpx.AsyncClient):
                raise ValueError("Workout HTTP client is unavailable")
            key = (
                decrypted_key(db, provider=task.provider, settings=settings)
                if backend is AIExecutionBackend.API
                else None
            )
            configured = build_task_provider(
                task,
                settings=settings,
                http_client=client,
                agent_http_client=(
                    client if backend is AIExecutionBackend.AGENT_SERVICE else None
                ),
                api_key=key,
            )
        except (AIConfigError, ValueError) as error:
            raise RuntimeError("AI Coach is not configured") from error
        ai_coach_provider = AiCoachProvider(configured.provider)
        provider_name = configured.provider_name
        model_id = configured.primary_model_id
        prompt_version = settings.workout_prompt_version
        generation_policy_version = settings.workout_policy_version
        ai_coach_fallback_models = configured.fallback_model_ids
        ai_coach_temperature = task.temperature
        ai_coach_max_output_tokens = task.max_output_tokens
        ai_coach_preferences = configured.routing_preferences
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
