from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import httpx

from app.ai.task_provider import build_task_provider
from app.body_analysis.admin_config.enums import AIExecutionBackend, AIProviderName, AITaskType
from app.body_analysis.admin_config.models import AITaskConfig
from app.body_analysis.admin_config.schemas import AITaskConfigUpdate
from app.body_analysis.providers import AgentServiceProvider, OpenRouterProvider
from app.body_analysis.service import AnalysisExecutionConfig
from app.config import Settings

AI_TIMEOUT_SECONDS = 420


def test_ai_model_timeout_defaults_are_seven_minutes_without_environment_overrides() -> None:
    settings = Settings(_env_file=None)

    assert settings.owner_video_codex_timeout_seconds == AI_TIMEOUT_SECONDS
    assert settings.opencode_zen_timeout_seconds == AI_TIMEOUT_SECONDS
    assert settings.openrouter_timeout_seconds == AI_TIMEOUT_SECONDS


def test_ai_task_and_analysis_timeout_defaults_are_seven_minutes() -> None:
    assert AITaskConfigUpdate().timeout_seconds == AI_TIMEOUT_SECONDS
    config = AnalysisExecutionConfig(
        provider_name="openrouter",
        primary_model="vision-primary",
        prompt_version="body-v1",
        schema_version="1.0",
    )

    assert config.timeout_seconds == AI_TIMEOUT_SECONDS


def test_orm_ai_task_timeout_default_is_seven_minutes(db) -> None:
    task = AITaskConfig(
        task_type=AITaskType.BODY_PHOTO_ANALYSIS,
        provider=AIProviderName.OPENROUTER,
    )
    db.add(task)
    db.flush()

    assert task.timeout_seconds == AI_TIMEOUT_SECONDS


def test_provider_constructor_defaults_are_seven_minutes() -> None:
    openrouter_client = httpx.AsyncClient()
    agent_client = httpx.AsyncClient()
    try:
        openrouter = OpenRouterProvider(openrouter_client, api_key=None)
        agent = AgentServiceProvider(
            agent_client,
            base_url="http://agent-service:9001",
            token=None,
            agent_name="codex",
        )

        assert openrouter._timeout.read == AI_TIMEOUT_SECONDS
        assert agent._timeout_seconds == AI_TIMEOUT_SECONDS
    finally:
        asyncio.run(openrouter_client.aclose())
        asyncio.run(agent_client.aclose())


def test_api_task_without_stored_timeout_uses_seven_minute_default(
    monkeypatch,
) -> None:
    provider = Mock(name="openrouter")
    factory = Mock(return_value=provider)
    monkeypatch.setattr("app.ai.task_provider.OpenRouterProvider", factory)
    task = SimpleNamespace(
        task_type=AITaskType.BODY_PHOTO_ANALYSIS,
        provider=AIProviderName.OPENROUTER,
        execution_backend=AIExecutionBackend.API,
        primary_model_id="openai/gpt-4.1",
        fallback_model_ids=[],
        routing_restrictions=[],
    )

    build_task_provider(
        task,
        settings=SimpleNamespace(
            openrouter_base_url="https://openrouter.test/v1",
            frontend_origin="http://localhost:5173",
            body_photo_storage_root="var/private/body-photos",
            food_photo_storage_root="var/private/food-photos",
        ),
        http_client=Mock(name="api-client"),
        agent_http_client=None,
        api_key="openrouter-secret",
    )

    assert factory.call_args.kwargs["timeout_seconds"] == AI_TIMEOUT_SECONDS
