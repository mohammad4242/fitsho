from datetime import UTC, datetime, timedelta
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.admin.dependencies import AdminUser, require_admin
from app.auth.cookies import require_trusted_origin
from app.auth.dependencies import AppSettings, DatabaseSession
from app.body_analysis.admin_config.crypto import CredentialEncryptionError
from app.body_analysis.admin_config.enums import AIProviderName, AITaskType
from app.body_analysis.admin_config.schemas import (
    AITaskConfigDetail,
    AITaskConfigUpdate,
    ModelCatalogRefreshResponse,
    ModelCatalogResponse,
    ProviderDetail,
    ProviderTestRequest,
    ProviderTestResponse,
)
from app.body_analysis.admin_config.service import (
    AIConfigError,
    credential_status,
    get_credential,
    list_models,
    list_task_configs,
    refresh_model_catalog,
    save_task_config,
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
