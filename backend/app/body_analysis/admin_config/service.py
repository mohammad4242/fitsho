from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import SecretStr
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.body_analysis.admin_config.crypto import CredentialCipher
from app.body_analysis.admin_config.enums import AIAuditAction, AIProviderName, AITaskType
from app.body_analysis.admin_config.models import (
    AIAuditEvent,
    AIModelCatalogEntry,
    AIProviderCredential,
    AITaskConfig,
)
from app.body_analysis.admin_config.schemas import (
    AITaskConfigDetail,
    AITaskConfigUpdate,
    CredentialStatus,
    ModelCatalogItem,
    ProviderTestResponse,
)
from app.body_analysis.providers import AIProviderError, OpenRouterProvider
from app.config import Settings


class AIConfigError(ValueError):
    pass


def credential_status(credential: AIProviderCredential | None) -> CredentialStatus:
    return CredentialStatus(
        configured=credential is not None,
        masked=f"••••{credential.key_last_four}" if credential is not None else None,
    )


def get_credential(db: Session, provider: AIProviderName) -> AIProviderCredential | None:
    return db.scalar(select(AIProviderCredential).where(AIProviderCredential.provider == provider))


def list_task_configs(db: Session) -> list[AITaskConfigDetail]:
    records = {record.task_type: record for record in db.scalars(select(AITaskConfig)).all()}
    credential = get_credential(db, AIProviderName.OPENROUTER)
    result: list[AITaskConfigDetail] = []
    for task_type in AITaskType:
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

    if payload.enabled and credential is None:
        raise AIConfigError("A provider credential is required before enabling this task")
    if payload.enabled and payload.primary_model_id is None:
        raise AIConfigError("A primary model is required before enabling this task")
    if payload.enabled:
        _validate_selected_models(
            db,
            task_type=task_type,
            provider=payload.provider,
            model_ids=[payload.primary_model_id, *payload.fallback_model_ids],
        )

    config = db.scalar(select(AITaskConfig).where(AITaskConfig.task_type == task_type))
    if config is None:
        config = AITaskConfig(task_type=task_type, provider=payload.provider)
        db.add(config)
    changed_fields: list[str] = []
    values: dict[str, Any] = {
        "provider": payload.provider,
        "enabled": payload.enabled,
        "primary_model_id": payload.primary_model_id,
        "fallback_model_ids": list(payload.fallback_model_ids),
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
