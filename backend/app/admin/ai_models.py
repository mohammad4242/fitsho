from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.schemas import AdminAiModelCreate, AdminAiModelUpdate, AdminAiRoutingUpdate
from app.ai.catalog import CatalogSyncResult, synchronize_zen_catalogue
from app.ai.models import (
    AiModel,
    AiModelTestOutcome,
    AiModelTestRun,
    AiRoutingSettings,
    RoutingMode,
)
from app.ai.opencode_zen import OpenCodeZenWorkoutPlanProvider
from app.ai.schemas import WorkoutProviderError
from app.config import Settings
from app.workouts.enums import WorkoutGenerationStatus
from app.workouts.models import WorkoutPlanGeneration


def list_ai_models(db: Session) -> tuple[AiRoutingSettings, list[AiModel]]:
    settings = db.get(AiRoutingSettings, 1)
    if settings is None:
        raise RuntimeError("AI routing settings are unavailable")
    models = list(db.scalars(select(AiModel).order_by(AiModel.priority, AiModel.model_id)))
    return settings, models


def list_generation_failures(db: Session, *, limit: int) -> list[WorkoutPlanGeneration]:
    return list(
        db.scalars(
            select(WorkoutPlanGeneration)
            .where(WorkoutPlanGeneration.status == WorkoutGenerationStatus.FAILED)
            .order_by(WorkoutPlanGeneration.created_at.desc())
            .limit(limit)
        )
    )


def list_ai_model_test_runs(db: Session, *, limit: int) -> list[AiModelTestRun]:
    return list(
        db.scalars(
            select(AiModelTestRun).order_by(AiModelTestRun.created_at.desc()).limit(limit)
        )
    )


def get_ai_model(db: Session, model_id: UUID) -> AiModel:
    model = db.get(AiModel, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI model not found")
    return model


def create_ai_model(db: Session, payload: AdminAiModelCreate) -> AiModel:
    existing = db.scalar(select(AiModel).where(AiModel.model_id == payload.model_id))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="AI model ID already exists",
        )
    model = AiModel(
        model_id=payload.model_id,
        display_name=payload.display_name,
        api_kind=payload.api_kind,
        billing_class=payload.billing_class,
        is_enabled=payload.is_enabled,
        priority=payload.priority,
        is_custom=True,
        classification_required=False,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def update_ai_model(db: Session, model: AiModel, payload: AdminAiModelUpdate) -> AiModel:
    changes = payload.model_dump(exclude_unset=True)
    requested_model_id = changes.pop("model_id", None)
    if requested_model_id is not None:
        if not model.is_custom:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Built-in AI model IDs cannot be changed",
            )
        duplicate = db.scalar(
            select(AiModel).where(
                AiModel.model_id == requested_model_id,
                AiModel.id != model.id,
            )
        )
        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="AI model ID already exists",
            )
        model.model_id = requested_model_id
    for field, value in changes.items():
        setattr(model, field, value)
    model.classification_required = model.api_kind is None or model.billing_class is None
    if model.classification_required:
        model.is_enabled = False
    db.commit()
    db.refresh(model)
    return model


def update_ai_routing(
    db: Session,
    payload: AdminAiRoutingUpdate,
) -> AiRoutingSettings:
    settings = db.get(AiRoutingSettings, 1)
    if settings is None:
        raise RuntimeError("AI routing settings are unavailable")
    if payload.mode is RoutingMode.MANUAL:
        if payload.manual_model_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="A manual AI model is required",
            )
        model = get_ai_model(db, payload.manual_model_id)
        if not model.is_enabled or model.classification_required:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="The selected AI model must be enabled and classified",
            )
        settings.manual_model_id = model.id
    settings.mode = payload.mode
    db.commit()
    db.refresh(settings)
    return settings


async def sync_zen_models(
    db: Session,
    client: httpx.AsyncClient,
    settings: Settings,
) -> CatalogSyncResult:
    headers: dict[str, str] = {}
    if settings.opencode_zen_api_key is not None:
        headers["Authorization"] = f"Bearer {settings.opencode_zen_api_key.get_secret_value()}"
    try:
        response = await client.get(
            f"{settings.opencode_zen_base_url.rstrip('/')}/models",
            headers=headers,
        )
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Zen model catalogue is unavailable",
        ) from error
    if (
        not isinstance(body, dict)
        or body.get("object") != "list"
        or not isinstance(body.get("data"), list)
        or any(
            not isinstance(item, dict)
            or not isinstance(item.get("id"), str)
            or not item["id"].strip()
            for item in body["data"]
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Zen model catalogue is invalid",
        )
    result = synchronize_zen_catalogue(db, {item["id"].strip() for item in body["data"]})
    db.commit()
    return result


async def check_ai_model(
    db: Session,
    model: AiModel,
    client: httpx.AsyncClient,
    settings: Settings,
) -> tuple[bool, AiModel, AiModelTestRun]:
    if model.api_kind is None or model.billing_class is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="AI model must be classified before testing",
        )
    provider = OpenCodeZenWorkoutPlanProvider(
        client,
        api_key=settings.opencode_zen_api_key,
        base_url=settings.opencode_zen_base_url,
        model=model.model_id,
        timeout_seconds=settings.opencode_zen_timeout_seconds,
        api_kind=model.api_kind,
    )
    model.last_checked_at = datetime.now(UTC)
    try:
        await provider.check_availability()
        await provider.check_model_test_contract()
    except WorkoutProviderError as error:
        model.last_error_code = error.code.value
        model.last_error_message = error.safe_message
        run = AiModelTestRun(
            ai_model_id=model.id,
            model_id=model.model_id,
            outcome=AiModelTestOutcome.FAILED,
            error_code=error.code.value,
            safe_error_message=error.safe_message,
        )
        db.add(run)
        db.commit()
        db.refresh(model)
        db.refresh(run)
        return False, model, run
    model.last_error_code = None
    model.last_error_message = None
    run = AiModelTestRun(
        ai_model_id=model.id,
        model_id=model.model_id,
        outcome=AiModelTestOutcome.SUCCEEDED,
    )
    db.add(run)
    db.commit()
    db.refresh(model)
    db.refresh(run)
    return True, model, run
