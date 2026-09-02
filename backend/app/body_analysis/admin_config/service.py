from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.body_analysis.admin_config.crypto import CredentialCipher
from app.body_analysis.admin_config.enums import (
    AIAgentServiceProxySource,
    AIAuditAction,
    AIExecutionBackend,
    AIProviderName,
    AITaskType,
)
from app.body_analysis.admin_config.models import (
    AIAgentProfileVerification,
    AIAgentServiceProxySetting,
    AIAuditEvent,
    AIModelCatalogEntry,
    AIProviderCredential,
    AITaskConfig,
)
from app.body_analysis.admin_config.schemas import (
    AgentServiceAuthActiveCancellationResponse,
    AgentServiceAuthInputRequest,
    AgentServiceAuthLogoutRequest,
    AgentServiceAuthLogoutResponse,
    AgentServiceAuthSessionResponse,
    AgentServiceAuthStartRequest,
    AgentServiceCapabilitiesResponse,
    AgentServiceProxyDetail,
    AgentServiceProxyRuntimeStatus,
    AgentServiceProxyUpdate,
    AgentServiceTestRequest,
    AgentServiceTestResponse,
    AITaskConfigDetail,
    AITaskConfigUpdate,
    CredentialStatus,
    ModelCatalogItem,
    ProviderTestResponse,
)
from app.body_analysis.providers import AIProviderError, OpenRouterProvider
from app.body_analysis.providers.models import ProviderErrorCode
from app.config import Settings


class AIConfigError(ValueError):
    pass


class AgentServiceAuthError(Exception):
    def __init__(self, code: str, status_code: int, safe_message: str) -> None:
        super().__init__(safe_message)
        self.code = code
        self.status_code = status_code
        self.safe_message = safe_message


_AGENT_SERVICE_TASKS = {
    AITaskType.WORKOUT_PLAN_GENERATION,
    AITaskType.BODY_PHOTO_ANALYSIS,
    AITaskType.FOOD_PHOTO_ESTIMATION,
    AITaskType.FOOD_PRICE_SEARCH,
}

_TASK_CONFIGURABLE_TASKS = tuple(AITaskType)

_AGENT_SAFE_MESSAGES: dict[ProviderErrorCode, str] = {
    ProviderErrorCode.NOT_CONFIGURED: "The Agent Service is not configured.",
    ProviderErrorCode.TIMEOUT: "The Agent Service request timed out.",
    ProviderErrorCode.CONNECTION_FAILURE: "The Agent Service is temporarily unreachable.",
    ProviderErrorCode.UNAUTHORIZED: "The Agent Service credential was rejected.",
    ProviderErrorCode.RATE_LIMITED: "The Agent Service is busy. Please try again.",
    ProviderErrorCode.PROVIDER_UNAVAILABLE: "The Agent Service is temporarily unavailable.",
    ProviderErrorCode.LOCATION_UNSUPPORTED: (
        "The provider does not support the current network location."
    ),
    ProviderErrorCode.INVALID_REQUEST: "The Agent Service rejected the request.",
    ProviderErrorCode.MALFORMED_RESPONSE: "The Agent Service returned a malformed response.",
}
_AGENT_SERVICE_ERROR_CODES = {
    "timeout": ProviderErrorCode.TIMEOUT,
    "unauthorized": ProviderErrorCode.UNAUTHORIZED,
    "rate_limited": ProviderErrorCode.RATE_LIMITED,
    "invalid_request": ProviderErrorCode.INVALID_REQUEST,
    "invalid_output": ProviderErrorCode.INVALID_OUTPUT,
    "model_not_found": ProviderErrorCode.MODEL_NOT_FOUND,
    "provider_unavailable": ProviderErrorCode.PROVIDER_UNAVAILABLE,
    "location_unsupported": ProviderErrorCode.LOCATION_UNSUPPORTED,
}
_AGENT_AUTH_ERRORS: dict[str, tuple[int, str]] = {
    "auth_in_progress": (409, "Authentication is already in progress."),
    "auth_session_not_found": (404, "The authentication session was not found."),
    "auth_session_expired": (410, "The authentication session has expired."),
    "auth_input_not_expected": (409, "Authentication input is not expected."),
    "auth_input_invalid": (422, "Authentication input is invalid."),
    "auth_unavailable": (503, "Authentication is temporarily unavailable."),
    "auth_manual_only": (409, "This Agent requires manual authentication."),
}


class _AgentServiceTestOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: Literal[True]
    agent: str
    model_id: str = Field(min_length=1, max_length=300)
    profile_id: str | None = Field(default=None, max_length=200)
    request_id: str = Field(min_length=1, max_length=300)
    duration_seconds: float = Field(ge=0)


def _mask_proxy_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        if not hostname:
            return None
        host = f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname
        port = f":{parsed.port}" if parsed.port is not None else ""
        credentials = (
            "****:****@"
            if parsed.username is not None or parsed.password is not None
            else ""
        )
        return f"{parsed.scheme.lower()}://{credentials}{host}{port}"
    except (TypeError, ValueError):
        return None


def credential_status(credential: AIProviderCredential | None) -> CredentialStatus:
    return CredentialStatus(
        configured=credential is not None,
        masked=f"********{credential.key_last_four}" if credential is not None else None,
    )


def get_credential(db: Session, provider: AIProviderName) -> AIProviderCredential | None:
    return db.scalar(select(AIProviderCredential).where(AIProviderCredential.provider == provider))


def list_task_configs(db: Session) -> list[AITaskConfigDetail]:
    records = {record.task_type: record for record in db.scalars(select(AITaskConfig)).all()}
    credential = get_credential(db, AIProviderName.OPENROUTER)
    result: list[AITaskConfigDetail] = []
    for task_type in _TASK_CONFIGURABLE_TASKS:
        record = records.get(task_type)
        result.append(config_detail(record, task_type=task_type, credential=credential))
    return result


def config_detail(
    config: AITaskConfig | None,
    *,
    task_type: AITaskType,
    credential: AIProviderCredential | None,
) -> AITaskConfigDetail:
    if config is None:
        return AITaskConfigDetail(
            task_type=task_type,
            provider=AIProviderName.OPENROUTER,
            execution_backend=(
                AIExecutionBackend.AGENT_SERVICE
                if task_type is AITaskType.FOOD_PRICE_SEARCH
                else AIExecutionBackend.API
            ),
            agent_name=None,
            agent_model_id=None,
            agent_profile_id=None,
            enabled=False,
            primary_model_id=None,
            fallback_model_ids=[],
            temperature=0.0,
            max_output_tokens=4096,
            timeout_seconds=45,
            minimum_confidence=0.7,
            max_cost_per_request=None,
            routing_restrictions=[],
            credential=credential_status(credential),
            last_successful_connection_test_at=None,
            last_model_catalog_refresh_at=None,
            last_error_code=None,
            last_error_message=None,
        )
    return AITaskConfigDetail(
        task_type=config.task_type,
        provider=config.provider,
        execution_backend=config.execution_backend,
        agent_name=config.agent_name,
        agent_model_id=config.agent_model_id,
        agent_profile_id=config.agent_profile_id,
        enabled=config.enabled,
        primary_model_id=config.primary_model_id,
        fallback_model_ids=list(config.fallback_model_ids),
        temperature=config.temperature,
        max_output_tokens=config.max_output_tokens,
        timeout_seconds=config.timeout_seconds,
        minimum_confidence=config.minimum_confidence,
        max_cost_per_request=config.max_cost_per_request,
        routing_restrictions=list(config.routing_restrictions),
        credential=credential_status(credential),
        last_successful_connection_test_at=config.last_successful_connection_test_at,
        last_model_catalog_refresh_at=config.last_model_catalog_refresh_at,
        last_error_code=config.last_error_code,
        last_error_message=config.last_error_message,
    )


def save_task_config(
    db: Session,
    *,
    task_type: AITaskType,
    payload: AITaskConfigUpdate,
    actor: User,
    settings: Settings,
) -> AITaskConfigDetail:
    config = db.scalar(select(AITaskConfig).where(AITaskConfig.task_type == task_type))
    credential = get_credential(db, payload.provider)
    credential_changed = False
    if payload.api_key is not None:
        plaintext = payload.api_key.get_secret_value().strip()
        if len(plaintext) < 8:
            raise AIConfigError("Provider credential is too short")
        cipher = CredentialCipher(settings.ai_credential_encryption_key)
        if credential is None:
            credential = AIProviderCredential(
                provider=payload.provider,
                encrypted_api_key=cipher.encrypt(plaintext),
                key_last_four=plaintext[-4:],
                updated_by_user_id=actor.id,
            )
            db.add(credential)
        else:
            credential.encrypted_api_key = cipher.encrypt(plaintext)
            credential.key_last_four = plaintext[-4:]
            credential.updated_by_user_id = actor.id
        credential_changed = True

    def effective(field: str, default: Any = None) -> Any:
        if field in payload.model_fields_set:
            return getattr(payload, field)
        return getattr(config, field, default)

    execution_backend = effective("execution_backend", AIExecutionBackend.API)
    agent_name = effective("agent_name")
    agent_model_id = effective("agent_model_id")
    agent_profile_id = effective("agent_profile_id")
    primary_model_id = effective("primary_model_id")
    fallback_model_ids = effective("fallback_model_ids", [])

    if (
        task_type is AITaskType.FOOD_PRICE_SEARCH
        and payload.enabled
        and execution_backend != AIExecutionBackend.AGENT_SERVICE
    ):
        raise AIConfigError(
            "FOOD_PRICE_SEARCH must use Agent Service for production price research"
        )

    if payload.enabled and execution_backend == AIExecutionBackend.AGENT_SERVICE:
        if task_type not in _AGENT_SERVICE_TASKS:
            raise AIConfigError("Agent service is not supported for this AI task")
        if agent_name is None or agent_profile_id is None or agent_model_id is None:
            raise AIConfigError(
                "Agent name, model, and verified profile are required before enabling this task"
            )
        verification = db.scalar(
            select(AIAgentProfileVerification).where(
                AIAgentProfileVerification.profile_id == agent_profile_id,
                AIAgentProfileVerification.task_type == task_type,
                AIAgentProfileVerification.status == "passed",
            )
        )
        if verification is None:
            raise AIConfigError("The selected Agent Service profile must pass its task test first")
    elif payload.enabled:
        if credential is None:
            raise AIConfigError("A provider credential is required before enabling this task")
        if primary_model_id is None:
            raise AIConfigError("A primary model is required before enabling this task")

    should_validate_api_models = execution_backend == AIExecutionBackend.API and (
        "primary_model_id" in payload.model_fields_set
        or "fallback_model_ids" in payload.model_fields_set
        or (payload.enabled and primary_model_id is not None)
    )
    if should_validate_api_models and (primary_model_id is not None or fallback_model_ids):
        _validate_selected_models(
            db,
            task_type=task_type,
            provider=payload.provider,
            model_ids=[primary_model_id, *fallback_model_ids],
        )

    if config is None:
        config = AITaskConfig(task_type=task_type, provider=payload.provider)
        db.add(config)
    changed_fields: list[str] = []
    values: dict[str, Any] = {
        "provider": payload.provider,
        "execution_backend": execution_backend,
        "agent_name": agent_name,
        "agent_model_id": agent_model_id,
        "agent_profile_id": agent_profile_id,
        "enabled": payload.enabled,
        "primary_model_id": primary_model_id,
        "fallback_model_ids": list(fallback_model_ids),
        "temperature": payload.temperature,
        "max_output_tokens": payload.max_output_tokens,
        "timeout_seconds": payload.timeout_seconds,
        "minimum_confidence": payload.minimum_confidence,
        "max_cost_per_request": payload.max_cost_per_request,
        "routing_restrictions": list(payload.routing_restrictions),
        "updated_by_user_id": actor.id,
    }
    for field, value in values.items():
        if getattr(config, field, None) != value:
            if field != "updated_by_user_id":
                changed_fields.append(field)
            setattr(config, field, value)
    db.add(
        AIAuditEvent(
            actor_user_id=actor.id,
            action=(
                AIAuditAction.CREDENTIAL_REPLACED
                if credential_changed
                else AIAuditAction.CONFIG_UPDATED
            ),
            task_type=task_type,
            provider=payload.provider,
            changed_fields=[
                *changed_fields,
                *(["credential_replaced"] if credential_changed else []),
            ],
        )
    )
    db.commit()
    db.refresh(config)
    return config_detail(config, task_type=task_type, credential=credential)


def decrypted_key(
    db: Session,
    *,
    provider: AIProviderName,
    settings: Settings,
) -> str:
    credential = get_credential(db, provider)
    if credential is None:
        raise AIConfigError("The AI provider is not configured")
    return CredentialCipher(settings.ai_credential_encryption_key).decrypt(
        credential.encrypted_api_key
    )


def openrouter_provider(
    client: httpx.AsyncClient,
    *,
    api_key: SecretStr | str | None,
    settings: Settings,
    timeout_seconds: float | None = None,
) -> OpenRouterProvider:
    return OpenRouterProvider(
        client,
        api_key=api_key,
        base_url=settings.openrouter_base_url,
        timeout_seconds=timeout_seconds or settings.openrouter_timeout_seconds,
        app_url=settings.frontend_origin,
    )


def _agent_service_token(settings: Settings) -> str:
    value: object = settings.agent_service_token
    if isinstance(value, SecretStr):
        value = value.get_secret_value()
    if not isinstance(value, str) or not value.strip():
        raise AIConfigError("Agent Service is not configured")
    token = value.strip()
    if settings.app_env == "production" and len(token) < 32:
        raise AIConfigError("Agent Service credential is too weak")
    return token


def _agent_service_headers(settings: Settings) -> dict[str, str]:
    return {"Authorization": f"Bearer {_agent_service_token(settings)}"}


async def _agent_service_json(
    client: httpx.AsyncClient,
    *,
    settings: Settings,
    method: str,
    path: str,
    json_body: dict[str, object] | None = None,
    preserve_auth_errors: bool = False,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    base_url = settings.agent_service_base_url.strip().rstrip("/")
    if not base_url:
        raise AIConfigError("Agent Service is not configured")
    headers = _agent_service_headers(settings)
    try:
        response = await client.request(
            method,
            f"{base_url}{path}",
            headers=headers,
            json=json_body,
            timeout=httpx.Timeout(
                timeout_seconds or settings.agent_service_connect_timeout_seconds
            ),
        )
    except httpx.TimeoutException as error:
        raise AIProviderError(
            ProviderErrorCode.TIMEOUT,
            _AGENT_SAFE_MESSAGES[ProviderErrorCode.TIMEOUT],
        ) from error
    except httpx.RequestError as error:
        raise AIProviderError(
            ProviderErrorCode.CONNECTION_FAILURE,
            _AGENT_SAFE_MESSAGES[ProviderErrorCode.CONNECTION_FAILURE],
        ) from error
    except Exception as error:
        raise AIProviderError(
            ProviderErrorCode.PROVIDER_UNAVAILABLE,
            _AGENT_SAFE_MESSAGES[ProviderErrorCode.PROVIDER_UNAVAILABLE],
        ) from error
    if response.status_code >= 400:
        if preserve_auth_errors:
            raise _agent_service_auth_http_error(response)
        raise _agent_service_http_error(response)
    try:
        payload = response.json()
    except (TypeError, ValueError) as error:
        raise AIProviderError(
            ProviderErrorCode.MALFORMED_RESPONSE,
            _AGENT_SAFE_MESSAGES[ProviderErrorCode.MALFORMED_RESPONSE],
            provider_status_code=response.status_code,
        ) from error
    if not isinstance(payload, dict):
        raise AIProviderError(
            ProviderErrorCode.MALFORMED_RESPONSE,
            _AGENT_SAFE_MESSAGES[ProviderErrorCode.MALFORMED_RESPONSE],
            provider_status_code=response.status_code,
        )
    return payload


def _agent_service_auth_http_error(response: httpx.Response) -> Exception:
    code_name: str | None = None
    try:
        body = response.json()
    except (TypeError, ValueError):
        body = None
    if isinstance(body, Mapping):
        error = body.get("error")
        if isinstance(error, Mapping) and isinstance(error.get("code"), str):
            code_name = error["code"]
    error_details = _AGENT_AUTH_ERRORS.get(code_name or "")
    if error_details is None:
        return _agent_service_http_error(response)
    status_code, safe_message = error_details
    return AgentServiceAuthError(code_name or "auth_unavailable", status_code, safe_message)


def _agent_service_http_error(response: httpx.Response) -> AIProviderError:
    code_name: str | None = None
    request_id = response.headers.get("x-request-id")
    try:
        body = response.json()
    except (TypeError, ValueError):
        body = None
    if isinstance(body, Mapping):
        error = body.get("error")
        if isinstance(error, Mapping):
            raw_code = error.get("code")
            if isinstance(raw_code, str):
                code_name = raw_code
            if request_id is None and isinstance(error.get("request_id"), str):
                request_id = error["request_id"]
    code = _AGENT_SERVICE_ERROR_CODES.get(code_name or "")
    if code is None:
        if response.status_code in {401, 403}:
            code = ProviderErrorCode.UNAUTHORIZED
        elif response.status_code in {408, 504}:
            code = ProviderErrorCode.TIMEOUT
        elif response.status_code == 429:
            code = ProviderErrorCode.RATE_LIMITED
        elif response.status_code == 404:
            code = ProviderErrorCode.MODEL_NOT_FOUND
        elif 400 <= response.status_code < 500:
            code = ProviderErrorCode.INVALID_REQUEST
        else:
            code = ProviderErrorCode.PROVIDER_UNAVAILABLE
    return AIProviderError(
        code,
        _AGENT_SAFE_MESSAGES.get(code, "The Agent Service request failed."),
        provider_status_code=response.status_code,
        provider_request_id=request_id,
    )


def _proxy_setting(db: Session) -> AIAgentServiceProxySetting | None:
    return db.scalar(select(AIAgentServiceProxySetting).where(AIAgentServiceProxySetting.id == 1))


def _proxy_detail(
    setting: AIAgentServiceProxySetting | None,
    *,
    runtime: AgentServiceProxyRuntimeStatus | None,
    agent_service_available: bool,
) -> AgentServiceProxyDetail:
    enabled = setting.enabled if setting is not None else True
    source = setting.source if setting is not None else AIAgentServiceProxySource.DEPLOYMENT_DEFAULT
    if runtime is not None:
        configured = runtime.configured
        default_configured = runtime.default_configured
        masked_proxy_url = runtime.masked_proxy_url
        applied = (
            runtime.enabled == enabled
            and runtime.source == source
            and (
                source is not AIAgentServiceProxySource.CUSTOM
                or runtime.masked_proxy_url == (setting.masked_proxy_url if setting else None)
            )
        )
    else:
        configured = (
            bool(setting and setting.encrypted_proxy_url)
            if source is AIAgentServiceProxySource.CUSTOM
            else False
        )
        default_configured = False
        masked_proxy_url = setting.masked_proxy_url if setting else None
        applied = False
    return AgentServiceProxyDetail(
        enabled=enabled,
        source=source,
        configured=configured,
        default_configured=default_configured,
        masked_proxy_url=masked_proxy_url,
        applied=applied,
        agent_service_available=agent_service_available,
        last_applied_at=setting.last_applied_at if setting else None,
        last_apply_error=setting.last_apply_error if setting else None,
    )


async def get_agent_service_proxy(
    db: Session,
    *,
    client: httpx.AsyncClient,
    settings: Settings,
) -> AgentServiceProxyDetail:
    setting = _proxy_setting(db)
    try:
        payload = await _agent_service_json(
            client,
            settings=settings,
            method="GET",
            path="/v1/runtime/proxy",
            timeout_seconds=max(5.0, settings.agent_service_connect_timeout_seconds),
        )
        runtime = AgentServiceProxyRuntimeStatus.model_validate(payload)
    except (AIConfigError, AIProviderError):
        return _proxy_detail(setting, runtime=None, agent_service_available=False)
    return _proxy_detail(setting, runtime=runtime, agent_service_available=True)


def _stored_proxy_url(
    setting: AIAgentServiceProxySetting | None,
    *,
    settings: Settings,
) -> str | None:
    if setting is None or setting.encrypted_proxy_url is None:
        return None
    return CredentialCipher(settings.ai_credential_encryption_key).decrypt(
        setting.encrypted_proxy_url
    )


def _proxy_apply_body(
    setting: AIAgentServiceProxySetting,
    *,
    proxy_url: str | None,
) -> dict[str, object]:
    body: dict[str, object] = {
        "enabled": setting.enabled,
        "source": setting.source.value,
    }
    if setting.source is AIAgentServiceProxySource.CUSTOM and proxy_url is not None:
        body["proxy_url"] = proxy_url
    return body


async def _apply_proxy_setting(
    setting: AIAgentServiceProxySetting,
    *,
    proxy_url: str | None,
    client: httpx.AsyncClient,
    settings: Settings,
) -> AgentServiceProxyRuntimeStatus:
    payload = await _agent_service_json(
        client,
        settings=settings,
        method="PUT",
        path="/v1/runtime/proxy",
        json_body=_proxy_apply_body(setting, proxy_url=proxy_url),
        timeout_seconds=max(5.0, settings.agent_service_connect_timeout_seconds),
    )
    try:
        runtime = AgentServiceProxyRuntimeStatus.model_validate(payload)
    except ValidationError as error:
        raise AIProviderError(
            ProviderErrorCode.MALFORMED_RESPONSE,
            _AGENT_SAFE_MESSAGES[ProviderErrorCode.MALFORMED_RESPONSE],
        ) from error
    if runtime.enabled != setting.enabled or runtime.source != setting.source:
        raise AIProviderError(
            ProviderErrorCode.MALFORMED_RESPONSE,
            _AGENT_SAFE_MESSAGES[ProviderErrorCode.MALFORMED_RESPONSE],
        )
    if (
        setting.source is AIAgentServiceProxySource.CUSTOM
        and runtime.masked_proxy_url != setting.masked_proxy_url
    ):
        raise AIProviderError(
            ProviderErrorCode.MALFORMED_RESPONSE,
            _AGENT_SAFE_MESSAGES[ProviderErrorCode.MALFORMED_RESPONSE],
        )
    return runtime


async def save_agent_service_proxy(
    db: Session,
    *,
    client: httpx.AsyncClient,
    settings: Settings,
    payload: AgentServiceProxyUpdate,
    actor: User,
) -> AgentServiceProxyDetail:
    setting = _proxy_setting(db)
    supplied_custom_url = (
        payload.proxy_url.get_secret_value() if payload.proxy_url is not None else None
    )
    custom_url = supplied_custom_url
    if payload.source is AIAgentServiceProxySource.CUSTOM:
        if custom_url is None:
            custom_url = _stored_proxy_url(setting, settings=settings)
        if payload.enabled and custom_url is None:
            raise AIConfigError("A custom proxy URL is required when proxy is enabled")

    if setting is None:
        setting = AIAgentServiceProxySetting(
            id=1,
            enabled=True,
            source=AIAgentServiceProxySource.DEPLOYMENT_DEFAULT,
        )
        db.add(setting)
    previous_enabled = setting.enabled
    previous_source = setting.source
    previous_masked_proxy_url = setting.masked_proxy_url
    setting.enabled = payload.enabled
    setting.source = payload.source
    if supplied_custom_url is not None:
        setting.encrypted_proxy_url = CredentialCipher(
            settings.ai_credential_encryption_key
        ).encrypt(supplied_custom_url)
        setting.masked_proxy_url = _mask_proxy_url(supplied_custom_url)
    changed_fields: list[str] = []
    if previous_enabled != setting.enabled:
        changed_fields.append("enabled")
    if previous_source != setting.source:
        changed_fields.append("source")
    if supplied_custom_url is not None and previous_masked_proxy_url != setting.masked_proxy_url:
        changed_fields.append("proxy_url_replaced")
    setting.updated_by_user_id = actor.id
    setting.last_apply_error = None
    db.add(
        AIAuditEvent(
            actor_user_id=actor.id,
            action=AIAuditAction.CONFIG_UPDATED,
            changed_fields=[f"agent_service_proxy.{field}" for field in changed_fields],
        )
    )
    db.commit()
    db.refresh(setting)

    try:
        runtime = await _apply_proxy_setting(
            setting,
            proxy_url=custom_url,
            client=client,
            settings=settings,
        )
    except (AIConfigError, AIProviderError) as error:
        setting.last_apply_error = (
            error.safe_message if isinstance(error, AIProviderError) else str(error)
        )
        db.commit()
        db.refresh(setting)
        return _proxy_detail(setting, runtime=None, agent_service_available=False)

    setting.last_applied_at = datetime.now(UTC)
    setting.last_apply_error = None
    db.commit()
    db.refresh(setting)
    return _proxy_detail(setting, runtime=runtime, agent_service_available=True)


async def sync_agent_service_proxy(
    db: Session,
    *,
    client: httpx.AsyncClient,
    settings: Settings,
) -> bool:
    setting = _proxy_setting(db)
    if setting is None:
        return True
    try:
        proxy_url = _stored_proxy_url(setting, settings=settings)
        await _apply_proxy_setting(
            setting,
            proxy_url=proxy_url,
            client=client,
            settings=settings,
        )
    except (AIConfigError, AIProviderError) as error:
        setting.last_apply_error = (
            error.safe_message if isinstance(error, AIProviderError) else str(error)
        )
        db.commit()
        return False
    setting.last_applied_at = datetime.now(UTC)
    setting.last_apply_error = None
    db.commit()
    return True


async def get_agent_service_capabilities(
    *,
    client: httpx.AsyncClient,
    settings: Settings,
    db: Session | None = None,
    task_type: AITaskType | None = None,
) -> AgentServiceCapabilitiesResponse:
    payload = await _agent_service_json(
        client,
        settings=settings,
        method="GET",
        path="/v1/capabilities",
        timeout_seconds=max(30.0, settings.agent_service_connect_timeout_seconds),
    )
    try:
        capabilities = AgentServiceCapabilitiesResponse.model_validate(payload)
        if db is None or task_type is None:
            return capabilities
        profile_ids = [
            profile.profile_id
            for runner in capabilities.runners
            for profile in (runner.profiles or [])
        ]
        if not profile_ids:
            return capabilities
        verifications = db.scalars(
            select(AIAgentProfileVerification).where(
                AIAgentProfileVerification.profile_id.in_(profile_ids),
                AIAgentProfileVerification.task_type == task_type,
            )
        ).all()
        by_profile = {item.profile_id: item for item in verifications}
        enriched_runners = []
        for runner in capabilities.runners:
            profiles = []
            for profile in runner.profiles or []:
                verification = by_profile.get(profile.profile_id)
                if verification is None:
                    profiles.append(profile)
                    continue
                status = (
                    "stale"
                    if verification.profile_fingerprint != profile.fingerprint
                    else verification.status
                )
                profiles.append(
                    profile.model_copy(
                        update={
                            "verification_status": status,
                            "verified_at": verification.checked_at,
                            "verification_error_code": verification.error_code,
                            "verification_safe_error_message": verification.safe_error_message,
                        }
                    )
                )
            enriched_runners.append(runner.model_copy(update={"profiles": profiles or None}))
        return capabilities.model_copy(update={"runners": enriched_runners})
    except ValidationError as error:
        raise AIProviderError(
            ProviderErrorCode.MALFORMED_RESPONSE,
            _AGENT_SAFE_MESSAGES[ProviderErrorCode.MALFORMED_RESPONSE],
        ) from error


async def test_agent_service(
    *,
    client: httpx.AsyncClient,
    settings: Settings,
    payload: AgentServiceTestRequest,
) -> AgentServiceTestResponse:
    checked_at = datetime.now(UTC)
    try:
        response_payload = await _agent_service_json(
            client,
            settings=settings,
            method="POST",
            path="/v1/test",
            json_body={
                "agent": payload.agent.value,
                "model_id": payload.model_id,
                **({"profile_id": payload.profile_id} if payload.profile_id else {}),
            },
        )
    except AIConfigError:
        return AgentServiceTestResponse(
            ok=False,
            agent=payload.agent,
            model_id=payload.model_id,
            profile_id=payload.profile_id,
            checked_at=checked_at,
            error_code=ProviderErrorCode.NOT_CONFIGURED.value,
            safe_error_message=_AGENT_SAFE_MESSAGES[ProviderErrorCode.NOT_CONFIGURED],
        )
    except AIProviderError as error:
        return AgentServiceTestResponse(
            ok=False,
            agent=payload.agent,
            model_id=payload.model_id,
            profile_id=payload.profile_id,
            checked_at=checked_at,
            error_code=error.code.value,
            safe_error_message=error.safe_message,
        )
    try:
        result = _AgentServiceTestOutput.model_validate(response_payload)
        if (
            result.agent != payload.agent.value
            or result.model_id != payload.model_id
            or (payload.profile_id is not None and result.profile_id != payload.profile_id)
        ):
            raise ValueError("test response identity mismatch")
    except (ValidationError, ValueError):
        return AgentServiceTestResponse(
            ok=False,
            agent=payload.agent,
            model_id=payload.model_id,
            checked_at=checked_at,
            error_code=ProviderErrorCode.MALFORMED_RESPONSE.value,
            safe_error_message=_AGENT_SAFE_MESSAGES[ProviderErrorCode.MALFORMED_RESPONSE],
        )
    return AgentServiceTestResponse(
        ok=True,
        agent=payload.agent,
        model_id=payload.model_id,
        profile_id=payload.profile_id,
        checked_at=checked_at,
        duration_seconds=result.duration_seconds,
    )


def _validate_agent_auth_response(payload: dict[str, Any]) -> AgentServiceAuthSessionResponse:
    try:
        return AgentServiceAuthSessionResponse.model_validate(payload)
    except ValidationError as error:
        raise AIProviderError(
            ProviderErrorCode.MALFORMED_RESPONSE,
            _AGENT_SAFE_MESSAGES[ProviderErrorCode.MALFORMED_RESPONSE],
        ) from error


async def start_agent_service_auth(
    *,
    client: httpx.AsyncClient,
    settings: Settings,
    payload: AgentServiceAuthStartRequest,
) -> AgentServiceAuthSessionResponse:
    response_payload = await _agent_service_json(
        client,
        settings=settings,
        method="POST",
        path="/v1/auth/start",
        json_body={
            "agent": payload.agent.value,
            **({"force_reauth": True} if payload.force_reauth else {}),
        },
        preserve_auth_errors=True,
    )
    return _validate_agent_auth_response(response_payload)


async def cancel_active_agent_service_auth(
    *,
    client: httpx.AsyncClient,
    settings: Settings,
    payload: AgentServiceAuthStartRequest,
) -> AgentServiceAuthActiveCancellationResponse:
    response_payload = await _agent_service_json(
        client,
        settings=settings,
        method="POST",
        path="/v1/auth/cancel-active",
        json_body={"agent": payload.agent.value},
        preserve_auth_errors=True,
    )
    try:
        return AgentServiceAuthActiveCancellationResponse.model_validate(response_payload)
    except ValidationError as error:
        raise AIProviderError(
            ProviderErrorCode.MALFORMED_RESPONSE,
            _AGENT_SAFE_MESSAGES[ProviderErrorCode.MALFORMED_RESPONSE],
        ) from error


async def logout_agent_service_auth(
    *,
    client: httpx.AsyncClient,
    settings: Settings,
    payload: AgentServiceAuthLogoutRequest,
) -> AgentServiceAuthLogoutResponse:
    response_payload = await _agent_service_json(
        client,
        settings=settings,
        method="POST",
        path="/v1/auth/logout",
        json_body={"agent": payload.agent.value},
        preserve_auth_errors=True,
    )
    try:
        return AgentServiceAuthLogoutResponse.model_validate(response_payload)
    except ValidationError as error:
        raise AIProviderError(
            ProviderErrorCode.MALFORMED_RESPONSE,
            _AGENT_SAFE_MESSAGES[ProviderErrorCode.MALFORMED_RESPONSE],
        ) from error


async def get_agent_service_auth(
    *,
    client: httpx.AsyncClient,
    settings: Settings,
    session_id: str,
) -> AgentServiceAuthSessionResponse:
    response_payload = await _agent_service_json(
        client,
        settings=settings,
        method="GET",
        path=f"/v1/auth/{session_id}",
        preserve_auth_errors=True,
    )
    return _validate_agent_auth_response(response_payload)


async def submit_agent_service_auth_input(
    *,
    client: httpx.AsyncClient,
    settings: Settings,
    session_id: str,
    payload: AgentServiceAuthInputRequest,
) -> AgentServiceAuthSessionResponse:
    response_payload = await _agent_service_json(
        client,
        settings=settings,
        method="POST",
        path=f"/v1/auth/{session_id}/input",
        json_body={"value": payload.value},
        preserve_auth_errors=True,
    )
    return _validate_agent_auth_response(response_payload)


async def cancel_agent_service_auth(
    *,
    client: httpx.AsyncClient,
    settings: Settings,
    session_id: str,
) -> AgentServiceAuthSessionResponse:
    response_payload = await _agent_service_json(
        client,
        settings=settings,
        method="DELETE",
        path=f"/v1/auth/{session_id}",
        preserve_auth_errors=True,
    )
    return _validate_agent_auth_response(response_payload)


async def test_provider_connection(
    db: Session,
    *,
    client: httpx.AsyncClient,
    provider_name: AIProviderName,
    supplied_key: SecretStr | None,
    actor: User,
    settings: Settings,
) -> ProviderTestResponse:
    key: SecretStr | str = supplied_key or decrypted_key(
        db, provider=provider_name, settings=settings
    )
    provider = openrouter_provider(client, api_key=key, settings=settings)
    now = datetime.now(UTC)
    try:
        result = await provider.test_connection()
    except AIProviderError as error:
        _record_provider_state(
            db,
            provider=provider_name,
            actor=actor,
            action=AIAuditAction.CONNECTION_TESTED,
            error_code=error.code.value,
            safe_error_message=error.safe_message,
        )
        return ProviderTestResponse(
            ok=False,
            checked_at=now,
            error_code=error.code.value,
            safe_error_message=error.safe_message,
        )
    _record_provider_state(
        db,
        provider=provider_name,
        actor=actor,
        action=AIAuditAction.CONNECTION_TESTED,
        connection_at=result.checked_at,
    )
    return ProviderTestResponse(
        ok=True,
        checked_at=result.checked_at,
        model_count=result.model_count,
    )


async def refresh_model_catalog(
    db: Session,
    *,
    client: httpx.AsyncClient,
    provider_name: AIProviderName,
    actor: User,
    settings: Settings,
) -> tuple[int, datetime]:
    key = decrypted_key(db, provider=provider_name, settings=settings)
    provider = openrouter_provider(client, api_key=key, settings=settings)
    models = await provider.list_models()
    refreshed_at = datetime.now(UTC)
    db.execute(delete(AIModelCatalogEntry).where(AIModelCatalogEntry.provider == provider_name))
    for item in models:
        db.add(
            AIModelCatalogEntry(
                provider=provider_name,
                model_id=item.model_id,
                display_name=item.display_name,
                provider_family=item.provider_family,
                supports_text_input=item.supports_text_input,
                supports_image_input=item.supports_image_input,
                supports_structured_output=item.supports_structured_output,
                context_length=item.context_length,
                input_price_per_token=item.input_price_per_token,
                output_price_per_token=item.output_price_per_token,
                available=item.available,
                refreshed_at=refreshed_at,
            )
        )
    _record_provider_state(
        db,
        provider=provider_name,
        actor=actor,
        action=AIAuditAction.MODEL_CATALOG_REFRESHED,
        catalog_at=refreshed_at,
        changed_fields=["model_catalog"],
        commit=False,
    )
    db.commit()
    return len(models), refreshed_at


def list_models(
    db: Session,
    *,
    task_type: AITaskType,
    search: str | None,
) -> tuple[list[ModelCatalogItem], datetime | None]:
    statement = select(AIModelCatalogEntry).where(AIModelCatalogEntry.available.is_(True))
    if task_type == AITaskType.BODY_PHOTO_ANALYSIS:
        statement = statement.where(AIModelCatalogEntry.supports_image_input.is_(True))
    else:
        statement = statement.where(AIModelCatalogEntry.supports_text_input.is_(True))
    if search:
        term = f"%{search.strip()}%"
        statement = statement.where(
            AIModelCatalogEntry.model_id.ilike(term) | AIModelCatalogEntry.display_name.ilike(term)
        )
    records = db.scalars(
        statement.order_by(
            AIModelCatalogEntry.supports_structured_output.desc(),
            AIModelCatalogEntry.display_name,
        )
    ).all()
    refreshed_at = max((item.refreshed_at for item in records), default=None)
    return [
        ModelCatalogItem(
            provider=item.provider,
            model_id=item.model_id,
            display_name=item.display_name,
            provider_family=item.provider_family,
            supports_text_input=item.supports_text_input,
            supports_image_input=item.supports_image_input,
            supports_structured_output=item.supports_structured_output,
            context_length=item.context_length,
            input_price_per_token=item.input_price_per_token,
            output_price_per_token=item.output_price_per_token,
            available=item.available,
        )
        for item in records
    ], refreshed_at


def _validate_selected_models(
    db: Session,
    *,
    task_type: AITaskType,
    provider: AIProviderName,
    model_ids: list[str | None],
) -> None:
    selected = [model_id for model_id in model_ids if model_id is not None]
    records = db.scalars(
        select(AIModelCatalogEntry).where(
            AIModelCatalogEntry.provider == provider,
            AIModelCatalogEntry.model_id.in_(selected),
            AIModelCatalogEntry.available.is_(True),
        )
    ).all()
    by_id = {record.model_id: record for record in records}
    missing = next((model_id for model_id in selected if model_id not in by_id), None)
    if missing is not None:
        raise AIConfigError("A selected model is not available in the refreshed catalog")
    for model_id in selected:
        record = by_id[model_id]
        if task_type == AITaskType.BODY_PHOTO_ANALYSIS and not record.supports_image_input:
            raise AIConfigError("Body-photo analysis requires an image-input model")
        if task_type != AITaskType.BODY_PHOTO_ANALYSIS and not record.supports_text_input:
            raise AIConfigError("This AI task requires a text-input model")


def _record_provider_state(
    db: Session,
    *,
    provider: AIProviderName,
    actor: User,
    action: AIAuditAction,
    connection_at: datetime | None = None,
    catalog_at: datetime | None = None,
    error_code: str | None = None,
    safe_error_message: str | None = None,
    changed_fields: list[str] | None = None,
    commit: bool = True,
) -> None:
    configs = db.scalars(select(AITaskConfig).where(AITaskConfig.provider == provider)).all()
    for config in configs:
        if connection_at is not None:
            config.last_successful_connection_test_at = connection_at
        if catalog_at is not None:
            config.last_model_catalog_refresh_at = catalog_at
        config.last_error_code = error_code
        config.last_error_message = safe_error_message
    db.add(
        AIAuditEvent(
            actor_user_id=actor.id,
            action=action,
            provider=provider,
            changed_fields=changed_fields or [],
        )
    )
    if commit:
        db.commit()
