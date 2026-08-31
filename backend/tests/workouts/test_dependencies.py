from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import cast
from unittest.mock import Mock

import httpx
import pytest
from fastapi import Request

from app.body_analysis.admin_config.enums import AIAgentName, AIExecutionBackend, AIProviderName
from app.body_analysis.providers import AgentServiceProvider, OpenRouterProvider
from app.config import Settings
from app.profile.enums import WorkoutGenerationMethod
from app.workouts.dependencies import get_workout_generation_service


def _request(*, api_client: httpx.AsyncClient, agent_client: httpx.AsyncClient) -> Request:
    return cast(
        Request,
        SimpleNamespace(
            app=SimpleNamespace(
                state=SimpleNamespace(
                    ai_http_client=api_client,
                    agent_http_client=agent_client,
                )
            )
        ),
    )


def _task(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "execution_backend": AIExecutionBackend.API,
        "provider": AIProviderName.OPENROUTER,
        "agent_name": None,
        "agent_model_id": None,
        "primary_model_id": "openai/gpt-4.1",
        "fallback_model_ids": ["openai/gpt-4.1-mini"],
        "enabled": True,
        "temperature": 0.2,
        "max_output_tokens": 512,
        "timeout_seconds": 9,
        "routing_restrictions": [],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _profile() -> SimpleNamespace:
    return SimpleNamespace(
        profile=SimpleNamespace(workout_generation_method=WorkoutGenerationMethod.AI)
    )


def test_workout_dependency_selects_agent_service_without_touching_api_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task = _task(
        execution_backend=AIExecutionBackend.AGENT_SERVICE,
        agent_name=AIAgentName.ANTIGRAVITY,
        agent_model_id="gemini-2.5-pro",
        primary_model_id=None,
        fallback_model_ids=[],
    )
    db = Mock()
    db.scalar.return_value = task
    user = SimpleNamespace(id="user-id")
    api_client = httpx.AsyncClient()
    agent_client = httpx.AsyncClient()
    decrypt = Mock(side_effect=AssertionError("Agent mode must not decrypt API credentials"))
    monkeypatch.setattr("app.workouts.dependencies.get_profile", lambda *_: _profile())
    monkeypatch.setattr("app.workouts.dependencies.decrypted_key", decrypt)

    try:
        service = get_workout_generation_service(
            db,
            _request(api_client=api_client, agent_client=agent_client),
            user,  # type: ignore[arg-type]
            Settings(app_env="test", agent_service_token="agent-service-test-token"),
        )
    finally:
        asyncio.run(api_client.aclose())
        asyncio.run(agent_client.aclose())

    assert service._ai_coach_provider is not None
    assert isinstance(service._ai_coach_provider._provider, AgentServiceProvider)
    assert service._settings.provider_name == "agent_service:antigravity"
    assert service._settings.model_id == "gemini-2.5-pro"
    assert service._settings.ai_coach_fallback_models == ()
    decrypt.assert_not_called()


def test_workout_dependency_keeps_openrouter_api_route(monkeypatch: pytest.MonkeyPatch) -> None:
    task = _task()
    db = Mock()
    db.scalar.return_value = task
    user = SimpleNamespace(id="user-id")
    api_client = httpx.AsyncClient()
    agent_client = httpx.AsyncClient()
    monkeypatch.setattr("app.workouts.dependencies.get_profile", lambda *_: _profile())
    monkeypatch.setattr(
        "app.workouts.dependencies.decrypted_key",
        lambda *args, **kwargs: "api-key",
    )

    try:
        service = get_workout_generation_service(
            db,
            _request(api_client=api_client, agent_client=agent_client),
            user,  # type: ignore[arg-type]
            Settings(app_env="test"),
        )
    finally:
        asyncio.run(api_client.aclose())
        asyncio.run(agent_client.aclose())

    assert service._ai_coach_provider is not None
    assert isinstance(service._ai_coach_provider._provider, OpenRouterProvider)
    assert service._settings.provider_name == "openrouter"
    assert service._settings.model_id == "openai/gpt-4.1"
    assert service._settings.ai_coach_fallback_models == ("openai/gpt-4.1-mini",)
