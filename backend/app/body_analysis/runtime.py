from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select

from app.auth.dependencies import AppSettings, DatabaseSession
from app.body_analysis.admin_config.enums import AIRoutingPolicy, AITaskType
from app.body_analysis.admin_config.models import AIModelCatalogEntry, AITaskConfig
from app.body_analysis.admin_config.service import (
    AIConfigError,
    decrypted_key,
    openrouter_provider,
)
from app.body_analysis.providers import AIProvider, ProviderRoutingPreferences
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
    try:
        policies = tuple(AIRoutingPolicy(item) for item in task.routing_restrictions)
        preferences = _provider_preferences(policies)
        _validate_budget_preflight(db, task)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Body analysis is temporarily unavailable",
        ) from error
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
            timeout_seconds=task.timeout_seconds,
            minimum_confidence=task.minimum_confidence,
            max_cost_per_request=task.max_cost_per_request,
            routing_preferences=preferences,
        ),
        storage=BodyPhotoStorage(settings),
    )


BodyAnalysisRuntimeDependency = Annotated[BodyAnalysisRuntime, Depends(get_body_analysis_runtime)]


def _provider_preferences(
    policies: tuple[AIRoutingPolicy, ...],
) -> ProviderRoutingPreferences:
    return ProviderRoutingPreferences(
        data_collection=(
            "deny" if AIRoutingPolicy.DENY_PROVIDER_DATA_COLLECTION in policies else None
        ),
        zdr=True if AIRoutingPolicy.ZERO_DATA_RETENTION in policies else None,
        require_parameters=(
            True if AIRoutingPolicy.REQUIRE_SUPPORTED_PARAMETERS in policies else None
        ),
    )


def _validate_budget_preflight(db: DatabaseSession, task: AITaskConfig) -> None:
    if task.max_cost_per_request is None:
        return
    model_ids = (task.primary_model_id, *task.fallback_model_ids)
    for model_id in model_ids:
        entry = db.scalar(
            select(AIModelCatalogEntry).where(
                AIModelCatalogEntry.provider == task.provider,
                AIModelCatalogEntry.model_id == model_id,
                AIModelCatalogEntry.available.is_(True),
                AIModelCatalogEntry.supports_image_input.is_(True),
                AIModelCatalogEntry.supports_structured_output.is_(True),
            )
        )
        if (
            entry is None
            or entry.context_length is None
            or entry.input_price_per_token is None
            or entry.output_price_per_token is None
            or entry.context_length < task.max_output_tokens
        ):
            raise ValueError("cannot evaluate image-analysis request cost")
        maximum_input_tokens = entry.context_length - task.max_output_tokens
        worst_case_cost = (
            entry.input_price_per_token * maximum_input_tokens
            + entry.output_price_per_token * task.max_output_tokens
        )
        if worst_case_cost > task.max_cost_per_request:
            raise ValueError("configured cost ceiling cannot cover the request bound")
