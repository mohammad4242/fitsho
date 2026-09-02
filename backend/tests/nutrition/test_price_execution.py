import asyncio
from types import SimpleNamespace

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
from app.body_analysis.providers.models import ProviderRoutingPreferences
from app.config import Settings
from app.nutrition.price_execution import (
    resolve_price_update_execution,
    resolve_single_food_price_researcher,
)


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


def test_single_food_price_research_defaults_to_seven_minute_timeout(
    db, test_settings: Settings, monkeypatch
) -> None:
    db.add(
        AITaskConfig(
            task_type=AITaskType.FOOD_PRICE_SEARCH,
            provider=AIProviderName.OPENROUTER,
            execution_backend=AIExecutionBackend.AGENT_SERVICE,
            agent_name=AIAgentName.ANTIGRAVITY,
            agent_model_id="gemini-price-model",
            enabled=True,
        )
    )
    db.commit()
    captured: dict[str, object] = {}

    def factory(_task, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            provider=object(),
            primary_model_id="gemini-price-model",
            fallback_model_ids=(),
            routing_preferences=ProviderRoutingPreferences(),
        )

    monkeypatch.setattr("app.nutrition.price_execution.build_task_provider", factory)
    client = httpx.AsyncClient()
    try:
        researcher = resolve_single_food_price_researcher(
            db,
            settings=test_settings,
            agent_http_client=client,
        )
    finally:
        asyncio.run(client.aclose())

    assert researcher is not None
    assert captured["timeout_seconds"] == 420.0


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


def test_cli_uses_resolved_agent_execution(test_settings: Settings, monkeypatch) -> None:
    from app.nutrition import price_update
    from app.nutrition.price_execution import PriceUpdateExecution

    marker = object()
    captured: dict[str, object] = {}

    class SessionContext:
        def __init__(self, _engine) -> None:
            pass

        def __enter__(self):
            return object()

        def __exit__(self, *_args) -> None:
            return None

    def resolve(_db, **kwargs):
        captured["agent_client"] = kwargs["agent_http_client"]
        return PriceUpdateExecution(providers=(), agent_researcher=marker)  # type: ignore[arg-type]

    async def update(_db, **kwargs):
        captured["providers"] = kwargs["providers"]
        captured["agent_researcher"] = kwargs["agent_researcher"]

    monkeypatch.setattr(price_update, "get_settings", lambda: test_settings)
    monkeypatch.setattr(price_update, "get_engine", lambda _url: object())
    monkeypatch.setattr(price_update, "Session", SessionContext)
    monkeypatch.setattr(price_update, "resolve_price_update_execution", resolve)
    monkeypatch.setattr(price_update, "run_price_update_async", update)

    asyncio.run(price_update.main())

    assert captured["providers"] == ()
    assert captured["agent_researcher"] is marker
    assert captured["agent_client"] is not None
