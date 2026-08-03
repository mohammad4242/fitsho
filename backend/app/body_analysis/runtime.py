from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select

from app.auth.dependencies import AppSettings, DatabaseSession
from app.body_analysis.admin_config.enums import AITaskType
from app.body_analysis.admin_config.models import AITaskConfig
from app.body_analysis.admin_config.service import (
    AIConfigError,
    decrypted_key,
    openrouter_provider,
)
from app.body_analysis.providers import AIProvider
from app.body_analysis.service import AnalysisExecutionConfig
from app.body_photos.storage import BodyPhotoStorage


@dataclass(frozen=True)
class BodyAnalysisRuntime:
    provider: AIProvider
    config: AnalysisExecutionConfig
    storage: BodyPhotoStorage


def get_body_analysis_runtime(
    request: Request,
    db: DatabaseSession,
    settings: AppSettings,
) -> BodyAnalysisRuntime:
    task = db.scalar(
        select(AITaskConfig).where(AITaskConfig.task_type == AITaskType.BODY_PHOTO_ANALYSIS)
    )
    if task is None or not task.enabled or not task.primary_model_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Body analysis is temporarily unavailable",
        )
    client = getattr(request.app.state, "ai_http_client", None)
    if not isinstance(client, httpx.AsyncClient):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Body analysis is temporarily unavailable",
        )
    try:
        key = decrypted_key(db, provider=task.provider, settings=settings)
    except AIConfigError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Body analysis is temporarily unavailable",
        ) from error
    return BodyAnalysisRuntime(
        provider=openrouter_provider(
            client,
            api_key=key,
            settings=settings,
            timeout_seconds=task.timeout_seconds,
        ),
        config=AnalysisExecutionConfig(
            provider_name=task.provider.value,
            primary_model=task.primary_model_id,
            fallback_models=tuple(task.fallback_model_ids),
            prompt_version="body-analysis-v1",
            schema_version="1.0",
            temperature=task.temperature,
            max_output_tokens=task.max_output_tokens,
        ),
        storage=BodyPhotoStorage(settings),
    )


BodyAnalysisRuntimeDependency = Annotated[BodyAnalysisRuntime, Depends(get_body_analysis_runtime)]
