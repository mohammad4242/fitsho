from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import httpx
import pytest
from fastapi import Request

from app.body_analysis.admin_config.enums import (
    AIAgentName,
    AIExecutionBackend,
    AIProviderName,
)
from app.body_analysis.providers import AgentServiceProvider, OpenRouterProvider
from app.body_analysis.runtime import get_body_analysis_runtime
from app.config import Settings


def _request(*, api_client: httpx.AsyncClient, agent_client: httpx.AsyncClient) -> SimpleNamespace:
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                ai_http_client=api_client,
                agent_http_client=agent_client,
            )
        )
    )


def _task(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "execution_backend": AIExecutionBackend.API,
        "provider": AIProviderName.OPENROUTER,
        "agent_name": None,
        "agent_model_id": None,
        "primary_model_id": "vision-primary",
        "fallback_model_ids": ["vision-fallback"],
        "enabled": True,
        "temperature": 0.1,
        "max_output_tokens": 1200,
        "timeout_seconds": 9,
        "minimum_confidence": 0.7,
        "max_cost_per_request": None,
        "routing_restrictions": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_runtime_uses_openrouter_and_keeps_api_cost_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = _task(max_cost_per_request=0.15)
    db = Mock()
    db.scalar.return_value = task
    api_client = httpx.AsyncClient()
    agent_client = httpx.AsyncClient()
    checked: list[object] = []
    monkeypatch.setattr(
        "app.body_analysis.runtime.decrypted_key",
        lambda *args, **kwargs: "api-key",
    )
    monkeypatch.setattr(
        "app.body_analysis.runtime._validate_budget_preflight",
        lambda database, configured_task: checked.append((database, configured_task)),
    )

    try:
        runtime = get_body_analysis_runtime(
            cast(Request, _request(api_client=api_client, agent_client=agent_client)),
            db,
            Settings(),
        )
    finally:
        asyncio.run(api_client.aclose())
        asyncio.run(agent_client.aclose())

    assert isinstance(runtime.provider, OpenRouterProvider)
    assert runtime.config.provider_name == "openrouter"
    assert runtime.config.primary_model == "vision-primary"
    assert runtime.config.fallback_models == ("vision-fallback",)
    assert runtime.config.max_cost_per_request == Decimal("0.15")
    assert checked == [(db, task)]


def test_runtime_uses_agent_service_and_skips_monetary_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = _task(
        execution_backend=AIExecutionBackend.AGENT_SERVICE,
        agent_name=AIAgentName.ANTIGRAVITY,
        agent_model_id="gemini-2.5-pro",
        primary_model_id=None,
        fallback_model_ids=[],
        max_cost_per_request=0.01,
    )
    db = Mock()
    db.scalar.return_value = task
    api_client = httpx.AsyncClient()
    agent_client = httpx.AsyncClient()
    checked = Mock()
    monkeypatch.setattr("app.body_analysis.runtime._validate_budget_preflight", checked)

    try:
        runtime = get_body_analysis_runtime(
            cast(Request, _request(api_client=api_client, agent_client=agent_client)),
            db,
            Settings(agent_service_token="agent-service-test-token", app_env="test"),
        )
    finally:
        asyncio.run(api_client.aclose())
        asyncio.run(agent_client.aclose())

    assert isinstance(runtime.provider, AgentServiceProvider)
    assert runtime.config.provider_name == "agent_service:antigravity"
    assert runtime.config.primary_model == "gemini-2.5-pro"
    assert runtime.config.fallback_models == ()
    assert runtime.config.max_cost_per_request is None
    checked.assert_not_called()
