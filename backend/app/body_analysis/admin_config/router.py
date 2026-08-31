from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.admin.dependencies import AdminUser, require_admin
from app.auth.cookies import require_trusted_origin
from app.auth.dependencies import AppSettings, DatabaseSession
from app.body_analysis.admin_config.crypto import CredentialEncryptionError
from app.body_analysis.admin_config.enums import AIProviderName, AITaskType
from app.body_analysis.admin_config.schemas import (
    AgentServiceAuthActiveCancellationResponse,
    AgentServiceAuthInputRequest,
    AgentServiceAuthSessionResponse,
    AgentServiceAuthStartRequest,
    AgentServiceCapabilitiesResponse,
    AgentServiceTestRequest,
    AgentServiceTestResponse,
    AITaskConfigDetail,
    AITaskConfigUpdate,
    ModelCatalogRefreshResponse,
    ModelCatalogResponse,
    ProviderDetail,
    ProviderTestRequest,
    ProviderTestResponse,
)
from app.body_analysis.admin_config.service import (
    AgentServiceAuthError,
    AIConfigError,
    cancel_active_agent_service_auth,
    cancel_agent_service_auth,
    credential_status,
    get_agent_service_auth,
    get_agent_service_capabilities,
    get_credential,
    list_models,
    list_task_configs,
    refresh_model_catalog,
    save_task_config,
    start_agent_service_auth,
    submit_agent_service_auth_input,
    test_agent_service,
    test_provider_connection,
)
from app.body_analysis.providers import AIProviderError

router = APIRouter(
    prefix="/api/v1/admin/ai",
    tags=["admin-ai-settings"],
    dependencies=[Depends(require_admin)],
)


def _client(request: Request) -> httpx.AsyncClient:
    client = getattr(request.app.state, "ai_http_client", None)
    if not isinstance(client, httpx.AsyncClient):
        raise RuntimeError("AI HTTP client is unavailable")
    return client


def _agent_client(request: Request) -> httpx.AsyncClient:
    client = getattr(request.app.state, "agent_http_client", None)
    if not isinstance(client, httpx.AsyncClient):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "AGENT_SERVICE_UNAVAILABLE",
                "message": "The Agent Service is temporarily unavailable.",
            },
        )
    return client


def _agent_provider_error(error: AIProviderError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail={"code": error.code.value, "message": error.safe_message},
    )


def _agent_auth_error(error: AgentServiceAuthError) -> HTTPException:
    return HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": error.safe_message},
    )


def _agent_not_configured(error: AIConfigError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "AGENT_SERVICE_NOT_CONFIGURED",
            "message": "The Agent Service is not configured.",
        },
    )


def _unprocessable(error: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(error))


@router.get("/providers", response_model=list[ProviderDetail])
def read_providers(db: DatabaseSession) -> list[ProviderDetail]:
    credential = get_credential(db, AIProviderName.OPENROUTER)
    return [
        ProviderDetail(
            provider=AIProviderName.OPENROUTER,
            display_name="OpenRouter",
            credential=credential_status(credential),
        )
    ]


@router.get("/task-configs", response_model=list[AITaskConfigDetail])
def read_task_configs(db: DatabaseSession) -> list[AITaskConfigDetail]:
    return list_task_configs(db)


@router.put(
    "/task-configs/{task_type}",
    response_model=AITaskConfigDetail,
    dependencies=[Depends(require_trusted_origin)],
)
def update_task_config(
    task_type: AITaskType,
    payload: AITaskConfigUpdate,
    db: DatabaseSession,
    settings: AppSettings,
    admin: AdminUser,
) -> AITaskConfigDetail:
    try:
        return save_task_config(
            db,
            task_type=task_type,
            payload=payload,
            actor=admin,
            settings=settings,
        )
    except (AIConfigError, CredentialEncryptionError) as error:
        raise _unprocessable(error) from None


@router.get("/models", response_model=ModelCatalogResponse)
def read_models(
    db: DatabaseSession,
    settings: AppSettings,
    task_type: AITaskType,
    search: Annotated[str | None, Query(max_length=100)] = None,
) -> ModelCatalogResponse:
    items, refreshed_at = list_models(db, task_type=task_type, search=search)
    stale_before = datetime.now(UTC) - timedelta(seconds=settings.ai_model_catalog_ttl_seconds)
    return ModelCatalogResponse(
        items=items,
        refreshed_at=refreshed_at,
        stale=refreshed_at is None or refreshed_at < stale_before,
    )


@router.post(
    "/providers/test",
    response_model=ProviderTestResponse,
    dependencies=[Depends(require_trusted_origin)],
)
async def test_provider(
    payload: ProviderTestRequest,
    request: Request,
    db: DatabaseSession,
    settings: AppSettings,
    admin: AdminUser,
) -> ProviderTestResponse:
    try:
        return await test_provider_connection(
            db,
            client=_client(request),
            provider_name=payload.provider,
            supplied_key=payload.api_key,
            actor=admin,
            settings=settings,
        )
    except (AIConfigError, CredentialEncryptionError) as error:
        raise _unprocessable(error) from None


@router.post(
    "/models/refresh",
    response_model=ModelCatalogRefreshResponse,
    dependencies=[Depends(require_trusted_origin)],
)
async def refresh_models(
    request: Request,
    db: DatabaseSession,
    settings: AppSettings,
    admin: AdminUser,
) -> ModelCatalogRefreshResponse:
    try:
        count, refreshed_at = await refresh_model_catalog(
            db,
            client=_client(request),
            provider_name=AIProviderName.OPENROUTER,
            actor=admin,
            settings=settings,
        )
    except (AIConfigError, CredentialEncryptionError) as error:
        raise _unprocessable(error) from None
    except AIProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=error.safe_message
        ) from None
    return ModelCatalogRefreshResponse(
        provider=AIProviderName.OPENROUTER,
        model_count=count,
        refreshed_at=refreshed_at,
    )


@router.get(
    "/agent-service/capabilities",
    response_model=AgentServiceCapabilitiesResponse,
)
async def read_agent_service_capabilities(
    request: Request,
    settings: AppSettings,
) -> AgentServiceCapabilitiesResponse:
    try:
        return await get_agent_service_capabilities(
            client=_agent_client(request),
            settings=settings,
        )
    except AIConfigError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "AGENT_SERVICE_NOT_CONFIGURED",
                "message": "The Agent Service is not configured.",
            },
        ) from error
    except AIProviderError as error:
        raise _agent_provider_error(error) from None


@router.post(
    "/agent-service/test",
    response_model=AgentServiceTestResponse,
    dependencies=[Depends(require_trusted_origin)],
)
async def test_agent_service_connection(
    payload: AgentServiceTestRequest,
    request: Request,
    settings: AppSettings,
) -> AgentServiceTestResponse:
    return await test_agent_service(
        client=_agent_client(request),
        settings=settings,
        payload=payload,
    )


@router.post(
    "/agent-service/auth/start",
    response_model=AgentServiceAuthSessionResponse,
    dependencies=[Depends(require_trusted_origin)],
)
async def start_agent_authentication(
    payload: AgentServiceAuthStartRequest,
    request: Request,
    settings: AppSettings,
) -> AgentServiceAuthSessionResponse:
    try:
        return await start_agent_service_auth(
            client=_agent_client(request),
            settings=settings,
            payload=payload,
        )
    except AIConfigError as error:
        raise _agent_not_configured(error) from None
    except AgentServiceAuthError as error:
        raise _agent_auth_error(error) from None
    except AIProviderError as error:
        raise _agent_provider_error(error) from None


@router.post(
    "/agent-service/auth/cancel-active",
    response_model=AgentServiceAuthActiveCancellationResponse,
    dependencies=[Depends(require_trusted_origin)],
)
async def cancel_active_agent_authentication(
    payload: AgentServiceAuthStartRequest,
    request: Request,
    settings: AppSettings,
) -> AgentServiceAuthActiveCancellationResponse:
    try:
        return await cancel_active_agent_service_auth(
            client=_agent_client(request),
            settings=settings,
            payload=payload,
        )
    except AIConfigError as error:
        raise _agent_not_configured(error) from None
    except AgentServiceAuthError as error:
        raise _agent_auth_error(error) from None
    except AIProviderError as error:
        raise _agent_provider_error(error) from None


@router.get(
    "/agent-service/auth/{session_id}",
    response_model=AgentServiceAuthSessionResponse,
)
async def read_agent_authentication(
    session_id: UUID,
    request: Request,
    settings: AppSettings,
) -> AgentServiceAuthSessionResponse:
    try:
        return await get_agent_service_auth(
            client=_agent_client(request),
            settings=settings,
            session_id=str(session_id),
        )
    except AIConfigError as error:
        raise _agent_not_configured(error) from None
    except AgentServiceAuthError as error:
        raise _agent_auth_error(error) from None
    except AIProviderError as error:
        raise _agent_provider_error(error) from None


@router.post(
    "/agent-service/auth/{session_id}/input",
    response_model=AgentServiceAuthSessionResponse,
    dependencies=[Depends(require_trusted_origin)],
)
async def submit_agent_authentication_input(
    session_id: UUID,
    payload: AgentServiceAuthInputRequest,
    request: Request,
    settings: AppSettings,
) -> AgentServiceAuthSessionResponse:
    try:
        return await submit_agent_service_auth_input(
            client=_agent_client(request),
            settings=settings,
            session_id=str(session_id),
            payload=payload,
        )
    except AIConfigError as error:
        raise _agent_not_configured(error) from None
    except AgentServiceAuthError as error:
        raise _agent_auth_error(error) from None
    except AIProviderError as error:
        raise _agent_provider_error(error) from None


@router.delete(
    "/agent-service/auth/{session_id}",
    response_model=AgentServiceAuthSessionResponse,
    dependencies=[Depends(require_trusted_origin)],
)
async def cancel_agent_authentication(
    session_id: UUID,
    request: Request,
    settings: AppSettings,
) -> AgentServiceAuthSessionResponse:
    try:
        return await cancel_agent_service_auth(
            client=_agent_client(request),
            settings=settings,
            session_id=str(session_id),
        )
    except AIConfigError as error:
        raise _agent_not_configured(error) from None
    except AgentServiceAuthError as error:
        raise _agent_auth_error(error) from None
    except AIProviderError as error:
        raise _agent_provider_error(error) from None
