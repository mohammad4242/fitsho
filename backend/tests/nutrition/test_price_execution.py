import asyncio

import httpx
import pytest

from app.body_analysis.admin_config.enums import (
    AIAgentName,
    AIExecutionBackend,
    AIProviderName,
    AITaskType,
)
from app.body_analysis.admin_config.models import AITaskConfig
from app.body_analysis.admin_config.service import AIConfigError
from app.config import Settings
from app.nutrition.price_execution import resolve_price_update_execution


def test_missing_or_disabled_food_price_task_uses_direct_providers(
    db, test_settings: Settings
) -> None:
    direct = object()
    price_client = httpx.AsyncClient()
    try:
        missing = resolve_price_update_execution(
            db,
            settings=test_settings,
            price_http_client=price_client,
            agent_http_client=None,
            direct_provider_factory=lambda: [direct],
        )
        assert missing.providers == (direct,)
        assert missing.agent_researcher is None

        db.add(
            AITaskConfig(
                task_type=AITaskType.FOOD_PRICE_SEARCH,
                provider=AIProviderName.OPENROUTER,
                execution_backend=AIExecutionBackend.API,
                enabled=False,
            )
        )
        db.commit()
        disabled = resolve_price_update_execution(
            db,
            settings=test_settings,
            price_http_client=price_client,
            agent_http_client=None,
            direct_provider_factory=lambda: [direct],
        )
        assert disabled.providers == (direct,)
        assert disabled.agent_researcher is None
    finally:
        asyncio.run(price_client.aclose())


def test_enabled_agent_food_price_task_selects_only_agent_researcher(
    db, test_settings: Settings
) -> None:
    test_settings.agent_service_token = "agent-service-test-token"
    db.add(
        AITaskConfig(
            task_type=AITaskType.FOOD_PRICE_SEARCH,
            provider=AIProviderName.OPENROUTER,
            execution_backend=AIExecutionBackend.AGENT_SERVICE,
            agent_name=AIAgentName.ANTIGRAVITY,
            agent_model_id="gemini-price-model",
            agent_profile_id="antigravity-price-profile",
            enabled=True,
        )
    )
    db.commit()
    price_client = httpx.AsyncClient()
    agent_client = httpx.AsyncClient()
    try:
        selected = resolve_price_update_execution(
            db,
            settings=test_settings,
            price_http_client=price_client,
            agent_http_client=agent_client,
            direct_provider_factory=lambda: pytest.fail("direct providers must not be selected"),
        )
    finally:
        asyncio.run(price_client.aclose())
        asyncio.run(agent_client.aclose())

    assert selected.providers == ()
    assert selected.agent_researcher is not None


def test_enabled_api_food_price_task_is_rejected_without_direct_fallback(
    db, test_settings: Settings
) -> None:
    db.add(
        AITaskConfig(
            task_type=AITaskType.FOOD_PRICE_SEARCH,
            provider=AIProviderName.OPENROUTER,
            execution_backend=AIExecutionBackend.API,
            enabled=True,
            primary_model_id="vendor/price-model",
        )
    )
    db.commit()
    price_client = httpx.AsyncClient()
    try:
        with pytest.raises(AIConfigError, match="Agent Service"):
            resolve_price_update_execution(
                db,
                settings=test_settings,
                price_http_client=price_client,
                agent_http_client=None,
                direct_provider_factory=lambda: pytest.fail("API mode must not fall back"),
            )
    finally:
        asyncio.run(price_client.aclose())
