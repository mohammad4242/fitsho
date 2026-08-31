from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.ai.task_provider import ConfiguredAIProvider, build_task_provider
from app.body_analysis.admin_config.enums import (
    AIAgentName,
    AIExecutionBackend,
    AIProviderName,
    AITaskType,
)


def _task(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "task_type": AITaskType.BODY_PHOTO_ANALYSIS,
        "provider": AIProviderName.OPENROUTER,
        "execution_backend": AIExecutionBackend.API,
        "agent_name": None,
        "agent_model_id": None,
        "primary_model_id": "openai/gpt-4.1",
        "fallback_model_ids": ["openai/gpt-4.1-mini"],
        "temperature": 0.0,
        "max_output_tokens": 512,
        "timeout_seconds": 45,
        "routing_restrictions": [],
        "max_cost_per_request": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_api_task_preserves_openrouter_provider_and_route_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api_provider = Mock(name="openrouter")
    openrouter_factory = Mock(return_value=api_provider)
    monkeypatch.setattr("app.ai.task_provider.OpenRouterProvider", openrouter_factory)

    configured = build_task_provider(
        _task(),
        settings=SimpleNamespace(openrouter_base_url="https://openrouter.test/v1"),
        http_client=Mock(name="api-client"),
        agent_http_client=Mock(name="agent-client"),
        api_key="openrouter-secret",
    )

    assert isinstance(configured, ConfiguredAIProvider)
    assert configured.provider is api_provider
    assert configured.provider_name == "openrouter"
    assert configured.primary_model_id == "openai/gpt-4.1"
    assert configured.fallback_model_ids == ("openai/gpt-4.1-mini",)
    assert configured.supports_cost_accounting is True
    openrouter_factory.assert_called_once()


def test_agent_task_selects_agent_service_and_exposes_agent_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    agent_provider = Mock(name="agent-service")
    agent_factory = Mock(return_value=agent_provider)
    monkeypatch.setattr("app.ai.task_provider.AgentServiceProvider", agent_factory)

    configured = build_task_provider(
        _task(
            execution_backend=AIExecutionBackend.AGENT_SERVICE,
            agent_name=AIAgentName.ANTIGRAVITY,
            agent_model_id="gemini-2.5-pro",
            primary_model_id=None,
            fallback_model_ids=[],
        ),
        settings=SimpleNamespace(
            agent_service_base_url="http://agent-service:9001",
            agent_service_token="agent-service-secret",
        ),
        http_client=Mock(name="api-client"),
        agent_http_client=Mock(name="agent-client"),
        api_key=None,
    )

    assert configured.provider is agent_provider
    assert configured.provider_name == "agent_service:antigravity"
    assert configured.primary_model_id == "gemini-2.5-pro"
    assert configured.fallback_model_ids == ()
    assert configured.supports_cost_accounting is False
    agent_factory.assert_called_once()


def test_configured_provider_is_frozen() -> None:
    configured = ConfiguredAIProvider(
        provider=Mock(),
        provider_name="openrouter",
        primary_model_id="model",
        fallback_model_ids=(),
        routing_preferences=SimpleNamespace(),
        supports_cost_accounting=True,
    )

    with pytest.raises(FrozenInstanceError):
        configured.provider_name = "agent_service:claude"  # type: ignore[misc]
