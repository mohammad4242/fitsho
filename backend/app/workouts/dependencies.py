from typing import Annotated

from fastapi import Depends

from app.auth.dependencies import DatabaseSession
from app.config import Settings, get_settings
from app.workouts.service import WorkoutGenerationService, WorkoutGenerationSettings


def get_workout_generation_service(
    db: DatabaseSession,
    settings: Annotated[Settings, Depends(get_settings)],
) -> WorkoutGenerationService:
    return WorkoutGenerationService(
        db,
        settings=WorkoutGenerationSettings(
            provider_name="fitsho_domain",
            model_id="program_engine_v1",
            prompt_version="none",
            generation_policy_version="resistance_training_v1",
            catalog_programming_version=settings.workout_catalog_programming_version,
            max_repair_attempts=0,
            cooldown_seconds=settings.workout_generation_cooldown_seconds,
            max_candidates=settings.workout_max_candidates,
            max_request_bytes=settings.workout_max_request_bytes,
            warmup_minutes=settings.workout_warmup_minutes,
            deterministic_fallback_enabled=False,
        ),
    )


WorkoutGenerationServiceDependency = Annotated[
    WorkoutGenerationService,
    Depends(get_workout_generation_service),
]
