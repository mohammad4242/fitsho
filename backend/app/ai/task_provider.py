from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import SecretStr

from app.body_analysis.admin_config.enums import (
    AIAgentName,
    AIExecutionBackend,
    AIProviderName,
    AIRoutingPolicy,
)
from app.body_analysis.providers import (
    AgentServiceProvider,
    AIProvider,
    OpenRouterProvider,
    ProviderRoutingPreferences,
)
from app.config import Settings
from app.private_media import PrivateMediaResolver


@dataclass(frozen=True)
class ConfiguredAIProvider:
    provider: AIProvider
    provider_name: str
    primary_model_id: str
    fallback_model_ids: tuple[str, ...]
    routing_preferences: ProviderRoutingPreferences
    supports_cost_accounting: bool


def build_task_provider(
    task: Any,
    *,
    settings: Settings,
    http_client: httpx.AsyncClient,
    agent_http_client: httpx.AsyncClient | None,
    api_key: SecretStr | str | None = None,
    timeout_seconds: float | None = None,
) -> ConfiguredAIProvider:
    backend = AIExecutionBackend(task.execution_backend)
    preferences = _routing_preferences(task.routing_restrictions)
    if backend is AIExecutionBackend.API:
        if AIProviderName(task.provider) is not AIProviderName.OPENROUTER:
            raise ValueError("unsupported API AI provider")
        primary_model_id = _required_model(task.primary_model_id, "primary_model_id")
        fallback_model_ids = _model_tuple(task.fallback_model_ids)
        provider = OpenRouterProvider(
            http_client,
            api_key=api_key,
            base_url=getattr(settings, "openrouter_base_url", "https://openrouter.ai/api/v1"),
            timeout_seconds=float(
                getattr(
                    task,
                    "timeout_seconds",
                    getattr(settings, "openrouter_timeout_seconds", 45),
                )
            ),
            app_url=getattr(settings, "frontend_origin", None),
            private_media_resolver=PrivateMediaResolver(settings),
        )
        return ConfiguredAIProvider(
            provider=provider,
            provider_name=AIProviderName.OPENROUTER.value,
            primary_model_id=primary_model_id,
            fallback_model_ids=fallback_model_ids,
            routing_preferences=preferences,
            supports_cost_accounting=True,
        )

    if backend is not AIExecutionBackend.AGENT_SERVICE:
        raise ValueError("unsupported AI execution backend")
    if agent_http_client is None:
        raise ValueError("Agent Service HTTP client is unavailable")
    agent_name = _required_agent(task.agent_name)
    primary_model_id = _required_model(task.agent_model_id, "agent_model_id")
    profile_id = _optional_profile(getattr(task, "agent_profile_id", None))
    token = getattr(settings, "agent_service_token", None)
    token_value = _secret_value(token)
    if token_value is None:
        raise ValueError("Agent Service token is not configured")
    if getattr(settings, "app_env", None) == "production" and (len(token_value) < 32):
        raise ValueError("production Agent Service mode requires a strong token")
    agent_provider: AIProvider = AgentServiceProvider(
        agent_http_client,
        base_url=getattr(settings, "agent_service_base_url", "http://agent-service:9001"),
        token=token,
        agent_name=agent_name,
        profile_id=profile_id,
        timeout_seconds=float(
            timeout_seconds if timeout_seconds is not None else task.timeout_seconds
        ),
        max_image_bytes=int(getattr(settings, "agent_service_max_image_bytes", 8 * 1024 * 1024)),
    )
    return ConfiguredAIProvider(
        provider=agent_provider,
        provider_name=f"agent_service:{agent_name}",
        primary_model_id=primary_model_id,
        fallback_model_ids=(),
        routing_preferences=preferences,
        supports_cost_accounting=False,
    )


def _routing_preferences(values: object) -> ProviderRoutingPreferences:
    if not isinstance(values, (list, tuple, set, frozenset)):
        values = ()
    policies = {AIRoutingPolicy(value) for value in values}
    return ProviderRoutingPreferences(
        data_collection=(
            "deny" if AIRoutingPolicy.DENY_PROVIDER_DATA_COLLECTION in policies else None
        ),
        zdr=True if AIRoutingPolicy.ZERO_DATA_RETENTION in policies else None,
        require_parameters=(
            True if AIRoutingPolicy.REQUIRE_SUPPORTED_PARAMETERS in policies else None
        ),
    )


def _required_model(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be configured")
    return value.strip()


def _required_agent(value: object) -> str:
    if not isinstance(value, (str, AIAgentName)):
        raise ValueError("agent_name must be configured")
    try:
        agent = AIAgentName(value)
    except ValueError as error:
        raise ValueError("agent_name must be configured") from error
    return agent.value


def _optional_profile(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("agent_profile_id must be configured")
    return value.strip()


def _model_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def _secret_value(value: object) -> str | None:
    if isinstance(value, SecretStr):
        value = value.get_secret_value()
    if isinstance(value, str):
        return value.strip() or None
    return None
