"""Resolve the configured execution mode for a food-price update."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.task_provider import build_task_provider
from app.body_analysis.admin_config.enums import AIExecutionBackend, AITaskType
from app.body_analysis.admin_config.models import AITaskConfig
from app.body_analysis.admin_config.service import AIConfigError
from app.body_analysis.providers.models import ModelRoute
from app.config import Settings
from app.nutrition.ai_price_research import AgentFoodPriceResearcher
from app.nutrition.price_providers import configured_providers
from app.nutrition.pricing import FoodPriceProvider


@dataclass(frozen=True)
class PriceUpdateExecution:
    providers: tuple[FoodPriceProvider, ...]
    agent_researcher: AgentFoodPriceResearcher | None


def resolve_price_update_execution(
    db: Session,
    *,
    settings: Settings,
    price_http_client: httpx.AsyncClient,
    agent_http_client: httpx.AsyncClient | None,
    direct_provider_factory: Callable[[], Iterable[FoodPriceProvider]] | None = None,
) -> PriceUpdateExecution:
    task = db.scalar(
        select(AITaskConfig).where(AITaskConfig.task_type == AITaskType.FOOD_PRICE_SEARCH)
    )
    if task is None or not task.enabled:
        providers = (
            direct_provider_factory()
            if direct_provider_factory is not None
            else configured_providers(settings, price_http_client)
        )
        return PriceUpdateExecution(tuple(providers), None)

    if AIExecutionBackend(task.execution_backend) is not AIExecutionBackend.AGENT_SERVICE:
        raise AIConfigError(
            "FOOD_PRICE_SEARCH must use Agent Service for production price research"
        )
    try:
        configured = build_task_provider(
            task,
            settings=settings,
            http_client=price_http_client,
            agent_http_client=agent_http_client,
        )
    except ValueError as error:
        raise AIConfigError(str(error)) from error
    researcher = AgentFoodPriceResearcher(
        configured.provider,
        route=ModelRoute(
            primary_model=configured.primary_model_id,
            fallback_models=configured.fallback_model_ids,
        ),
        preferences=configured.routing_preferences,
        temperature=float(task.temperature),
        max_output_tokens=int(task.max_output_tokens),
    )
    return PriceUpdateExecution((), researcher)


def resolve_single_food_price_researcher(
    db: Session,
    *,
    settings: Settings,
    agent_http_client: httpx.AsyncClient | None,
    timeout_seconds: float = 420.0,
) -> AgentFoodPriceResearcher | None:
    task = db.scalar(
        select(AITaskConfig).where(AITaskConfig.task_type == AITaskType.FOOD_PRICE_SEARCH)
    )
    if task is None or not task.enabled:
        return None

    if AIExecutionBackend(task.execution_backend) is not AIExecutionBackend.AGENT_SERVICE:
        raise AIConfigError(
            "FOOD_PRICE_SEARCH must use Agent Service for production price research"
        )
    try:
        configured = build_task_provider(
            task,
            settings=settings,
            http_client=agent_http_client or httpx.AsyncClient(),
            agent_http_client=agent_http_client,
            timeout_seconds=timeout_seconds,
        )
    except ValueError as error:
        raise AIConfigError(str(error)) from error
    return AgentFoodPriceResearcher(
        configured.provider,
        route=ModelRoute(
            primary_model=configured.primary_model_id,
            fallback_models=configured.fallback_model_ids,
        ),
        preferences=configured.routing_preferences,
        temperature=float(task.temperature),
        max_output_tokens=int(task.max_output_tokens),
    )
