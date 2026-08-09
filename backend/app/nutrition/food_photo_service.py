from __future__ import annotations

import base64
import hashlib
import io
import os
import tempfile
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from uuid import UUID, uuid4

import httpx
from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.body_analysis.admin_config.enums import AIProviderName, AITaskType
from app.body_analysis.admin_config.models import AITaskConfig
from app.body_analysis.admin_config.service import decrypted_key, openrouter_provider
from app.body_analysis.providers.models import (
    AIProviderError,
    ImageInput,
    ModelRoute,
    ProviderRoutingPreferences,
    StructuredGenerationRequest,
)
from app.config import Settings
from app.nutrition.enums import (
    EstimateConfidence,
    FoodVerificationStatus,
    NutritionConsumptionSource,
)
from app.nutrition.food_catalogue import normalize_food_alias
from app.nutrition.models import (
    NutritionCatalogueFood,
    NutritionConsumptionEntry,
    NutritionFoodPhotoEstimate,
)
from app.nutrition.security import audit_security_event, record_operational_event
from app.nutrition.tracking_service import actual_intake_warnings


class FoodPhotoError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code


class EstimatedPhotoItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name_guess: str = Field(min_length=1, max_length=160)
    estimated_amount: float = Field(gt=0, le=10000)
    unit: str = Field(pattern="^(g|ml|item|unknown)$")
    confidence: float = Field(ge=0, le=1)
    visible_evidence: list[str] = Field(max_length=10)
    uncertainties: list[str] = Field(max_length=10)


class FoodPhotoOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meal_name_guess: str | None = Field(default=None, max_length=160)
    items: list[EstimatedPhotoItem] = Field(min_length=1, max_length=20)
    overall_confidence: float = Field(ge=0, le=1)
    needs_user_confirmation: bool


RESPONSE_SCHEMA = FoodPhotoOutput.model_json_schema()


def replay_idempotent_photo(
    db: Session, user_id: UUID, idempotency_key: str | None
) -> dict[str, object] | None:
    if idempotency_key is None:
        return None
    key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest()
    previous = db.scalar(
        select(NutritionFoodPhotoEstimate).where(
            NutritionFoodPhotoEstimate.user_id == user_id,
            NutritionFoodPhotoEstimate.idempotency_key_hash == key_hash,
        )
    )
    return photo_response(previous) if previous is not None else None


def food_photo_storage_path(root: Path, key: str) -> Path:
    resolved_root = root.resolve()
    relative = PurePosixPath(key)
    if relative.is_absolute() or len(relative.parts) != 2 or ".." in relative.parts:
        raise FoodPhotoError("INVALID_STORAGE_KEY")
    path = resolved_root.joinpath(*relative.parts)
    if not path.is_relative_to(resolved_root):
        raise FoodPhotoError("INVALID_STORAGE_KEY")
    return path


def _normalize_image(content: bytes, max_pixels: int) -> tuple[bytes, str]:
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.width * image.height > max_pixels:
                raise FoodPhotoError("INVALID_FOOD_PHOTO")
            image.load()
            converted = image.convert("RGB")
            output = io.BytesIO()
            converted.save(output, format="JPEG", quality=88, optimize=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        raise FoodPhotoError("INVALID_FOOD_PHOTO") from error
    normalized = output.getvalue()
    if not normalized:
        raise FoodPhotoError("INVALID_FOOD_PHOTO")
    return normalized, "image/jpeg"


def _store(root: Path, content: bytes) -> str:
    identifier = uuid4().hex
    key = f"{identifier[:2]}/{identifier}.jpg"
    destination = food_photo_storage_path(root, key)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except OSError as error:
        if temporary:
            temporary.unlink(missing_ok=True)
        raise FoodPhotoError("FOOD_PHOTO_STORAGE_UNAVAILABLE") from error
    return key


def _map_items(db: Session, output: FoodPhotoOutput) -> list[dict[str, object]]:
    foods = db.scalars(
        select(NutritionCatalogueFood)
        .where(NutritionCatalogueFood.verification_status == FoodVerificationStatus.VERIFIED)
        .options(selectinload(NutritionCatalogueFood.aliases))
    ).all()
    names: dict[str, NutritionCatalogueFood] = {}
    for food in foods:
        for value in (
            food.slug,
            food.name_fa,
            food.name_en,
            *(alias.alias for alias in food.aliases),
        ):
            names[normalize_food_alias(value)] = food
    mapped: list[dict[str, object]] = []
    for item in output.items:
        matched_food = names.get(normalize_food_alias(item.name_guess))
        mapped.append(
            {
                **item.model_dump(),
                "item_id": str(uuid4()),
                "food_id": str(matched_food.id) if matched_food else None,
                "food_slug": matched_food.slug if matched_food else None,
                "mapping_status": "resolved" if matched_food else "unresolved",
            }
        )
    return mapped


async def estimate_photo(
    db: Session,
    user_id: UUID,
    file: UploadFile,
    consent: bool,
    settings: Settings,
    client: httpx.AsyncClient,
    idempotency_key: str | None = None,
) -> dict[str, object]:
    if not consent:
        raise FoodPhotoError("THIRD_PARTY_PROCESSING_CONSENT_REQUIRED")
    key_hash = hashlib.sha256(idempotency_key.encode()).hexdigest() if idempotency_key else None
    replayed = replay_idempotent_photo(db, user_id, idempotency_key)
    if replayed is not None:
        return replayed
    config = db.scalar(
        select(AITaskConfig).where(AITaskConfig.task_type == AITaskType.FOOD_PHOTO_ESTIMATION)
    )
    if config is None or not config.enabled or not config.primary_model_id:
        raise FoodPhotoError("FOOD_PHOTO_ESTIMATION_DISABLED")
    content = await file.read(settings.food_photo_max_bytes + 1)
    if len(content) > settings.food_photo_max_bytes:
        raise FoodPhotoError("FOOD_PHOTO_TOO_LARGE")
    normalized, mime_type = _normalize_image(content, settings.food_photo_max_pixels)
    key = _store(settings.food_photo_storage_root, normalized)
    provider = openrouter_provider(
        client,
        api_key=decrypted_key(db, provider=AIProviderName.OPENROUTER, settings=settings),
        settings=settings,
        timeout_seconds=config.timeout_seconds,
    )
    preferences = set(config.routing_restrictions)
    request = StructuredGenerationRequest(
        system_prompt=(
            "Identify only visible foods and estimate portions. Return uncertainty. "
            "Do not provide calories, medical advice, allergy claims, or suitability."
        ),
        input_payload={"instruction": "Analyze this food image without personal data."},
        response_schema=RESPONSE_SCHEMA,
        schema_name="fitsho_food_photo_estimate_v1",
        route=ModelRoute(
            primary_model=config.primary_model_id,
            fallback_models=tuple(config.fallback_model_ids),
        ),
        provider_preferences=ProviderRoutingPreferences(
            data_collection="deny" if "deny_provider_data_collection" in preferences else None,
            zdr=True if "zero_data_retention" in preferences else None,
            require_parameters=True if "require_supported_parameters" in preferences else None,
        ),
        temperature=config.temperature,
        max_output_tokens=config.max_output_tokens,
    )
    try:
        result = await provider.analyze_images(
            request,
            images=(
                ImageInput(
                    label="food_photo",
                    mime_type="image/jpeg",
                    base64_data=base64.b64encode(normalized).decode("ascii"),
                ),
            ),
        )
        output = FoodPhotoOutput.model_validate(result.payload)
    except (AIProviderError, ValueError) as error:
        food_photo_storage_path(settings.food_photo_storage_root, key).unlink(missing_ok=True)
        record_operational_event(
            db,
            category="ai",
            event_name="food_photo_estimation",
            status="error",
            provider="openrouter",
            counters={"requests": 1, "errors": 1},
        )
        db.commit()
        raise FoodPhotoError("FOOD_PHOTO_PROVIDER_UNAVAILABLE") from error
    now = datetime.now(UTC)
    row = NutritionFoodPhotoEstimate(
        user_id=user_id,
        storage_key=key,
        sha256=hashlib.sha256(normalized).hexdigest(),
        content_type=mime_type,
        byte_size=len(normalized),
        idempotency_key_hash=key_hash,
        status="estimated",
        provider="openrouter",
        model_id=result.model_id,
        provider_request_id=result.provider_request_id,
        raw_estimate=output.model_dump(mode="json"),
        mapped_items=_map_items(db, output),
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        estimated_cost=result.cost,
        consented_at=now,
        expires_at=now + timedelta(days=settings.food_photo_retention_days),
    )
    db.add(row)
    db.flush()
    audit_security_event(
        db,
        actor_user_id=user_id,
        owner_user_id=user_id,
        event_type="food_photo_estimated",
        resource_type="food_photo_estimate",
        resource_id=row.id,
        metadata={"provider": "openrouter", "byte_size": len(normalized)},
    )
    record_operational_event(
        db,
        category="ai",
        event_name="food_photo_estimation",
        status="success",
        provider="openrouter",
        counters={
            "requests": 1,
            "errors": 0,
            "input_tokens": result.input_tokens or 0,
            "output_tokens": result.output_tokens or 0,
        },
    )
    db.commit()
    db.refresh(row)
    return photo_response(row)


def photo_response(row: NutritionFoodPhotoEstimate) -> dict[str, object]:
    items = [
        {**item, "item_id": item.get("item_id") or f"legacy-{index}"}
        for index, item in enumerate(row.mapped_items)
    ]
    return {
        "id": row.id,
        "status": row.status,
        "items": items,
        "overall_confidence": row.raw_estimate.get("overall_confidence"),
        "needs_user_confirmation": True,
        "model_id": row.model_id,
        "expires_at": row.expires_at,
    }


def correct_photo_item(
    db: Session,
    user_id: UUID,
    estimate_id: UUID,
    item_id: str,
    *,
    food_id: UUID | None,
    estimated_amount: Decimal | None,
    remove: bool,
) -> dict[str, object]:
    row = db.scalar(
        select(NutritionFoodPhotoEstimate)
        .where(
            NutritionFoodPhotoEstimate.id == estimate_id,
            NutritionFoodPhotoEstimate.user_id == user_id,
            NutritionFoodPhotoEstimate.status == "estimated",
        )
        .with_for_update()
    )
    if row is None:
        raise FoodPhotoError("FOOD_PHOTO_ESTIMATE_NOT_FOUND")
    items = [dict(item) for item in row.mapped_items]
    index = next(
        (
            position
            for position, item in enumerate(items)
            if (item.get("item_id") or f"legacy-{position}") == item_id
        ),
        None,
    )
    if index is None:
        raise FoodPhotoError("FOOD_PHOTO_ITEM_NOT_FOUND")
    if remove:
        items.pop(index)
    else:
        item = items[index]
        item["item_id"] = item.get("item_id") or item_id
        if estimated_amount is not None:
            item["estimated_amount"] = float(estimated_amount)
        if food_id is not None:
            food = db.scalar(
                select(NutritionCatalogueFood).where(
                    NutritionCatalogueFood.id == food_id,
                    NutritionCatalogueFood.verification_status
                    == FoodVerificationStatus.VERIFIED,
                )
            )
            if food is None:
                raise FoodPhotoError("FOOD_NOT_FOUND")
            item.update(
                food_id=str(food.id),
                food_slug=food.slug,
                name_guess=food.name_fa,
                unit="g",
                mapping_status="resolved",
            )
        items[index] = item
    row.mapped_items = items
    audit_security_event(
        db,
        actor_user_id=user_id,
        owner_user_id=user_id,
        event_type="food_photo_item_corrected",
        resource_type="food_photo_estimate",
        resource_id=row.id,
        metadata={"item_id": item_id, "removed": remove},
    )
    db.commit()
    db.refresh(row)
    return photo_response(row)


def confirm_photo(
    db: Session, user_id: UUID, estimate_id: UUID, entry_date: date
) -> list[dict[str, object]]:
    row = db.scalar(
        select(NutritionFoodPhotoEstimate).where(
            NutritionFoodPhotoEstimate.id == estimate_id,
            NutritionFoodPhotoEstimate.user_id == user_id,
            NutritionFoodPhotoEstimate.status == "estimated",
        )
    )
    if row is None:
        raise FoodPhotoError("FOOD_PHOTO_ESTIMATE_NOT_FOUND")
    created: list[NutritionConsumptionEntry] = []
    for item in row.mapped_items:
        food_id = item.get("food_id")
        if not food_id or item.get("unit") != "g":
            continue
        food = db.scalar(
            select(NutritionCatalogueFood)
            .where(
                NutritionCatalogueFood.id == UUID(str(food_id)),
                NutritionCatalogueFood.verification_status
                == FoodVerificationStatus.VERIFIED,
            )
            .options(selectinload(NutritionCatalogueFood.compositions))
        )
        if food is None:
            continue
        grams = float(str(item["estimated_amount"]))
        nutrients = {
            composition.nutrient_code: str(
                composition.value_per_100g * (Decimal(str(grams)) / Decimal("100"))
            )
            for composition in food.compositions
        }
        entry = NutritionConsumptionEntry(
            user_id=user_id,
            entry_date=entry_date,
            food_id=food.id,
            display_name=food.name_fa,
            quantity_grams=Decimal(str(grams)),
            source=NutritionConsumptionSource.PHOTO_ESTIMATED_CONFIRMED,
            confidence=EstimateConfidence.LOW,
            user_confirmed=True,
            nutrients=nutrients,
            warning_codes=list(
                dict.fromkeys(
                    ["PHOTO_ESTIMATE_APPROXIMATE", *actual_intake_warnings(db, user_id, food)]
                )
            ),
        )
        db.add(entry)
        created.append(entry)
    if not created:
        raise FoodPhotoError("UNRESOLVED_ITEMS_REQUIRE_EDIT")
    row.status = "confirmed"
    row.confirmed_at = datetime.now(UTC)
    db.commit()
    return [{"id": item.id, "display_name": item.display_name} for item in created]


def delete_photo(db: Session, user_id: UUID, estimate_id: UUID, settings: Settings) -> None:
    row = db.scalar(
        select(NutritionFoodPhotoEstimate).where(
            NutritionFoodPhotoEstimate.id == estimate_id,
            NutritionFoodPhotoEstimate.user_id == user_id,
        )
    )
    if row is None:
        raise FoodPhotoError("FOOD_PHOTO_ESTIMATE_NOT_FOUND")
    food_photo_storage_path(settings.food_photo_storage_root, row.storage_key).unlink(
        missing_ok=True
    )
    row.status = "deleted"
    row.deleted_at = datetime.now(UTC)
    row.raw_estimate = {}
    row.mapped_items = []
    audit_security_event(
        db,
        actor_user_id=user_id,
        owner_user_id=user_id,
        event_type="food_photo_deleted",
        resource_type="food_photo_estimate",
        resource_id=row.id,
    )
    db.commit()


def authorize_photo_access(
    db: Session, user_id: UUID, estimate_id: UUID
) -> NutritionFoodPhotoEstimate:
    row = db.scalar(
        select(NutritionFoodPhotoEstimate).where(
            NutritionFoodPhotoEstimate.id == estimate_id,
            NutritionFoodPhotoEstimate.user_id == user_id,
            NutritionFoodPhotoEstimate.deleted_at.is_(None),
        )
    )
    if row is None:
        raise FoodPhotoError("FOOD_PHOTO_ESTIMATE_NOT_FOUND")
    return row


def open_photo(
    db: Session, user_id: UUID, estimate_id: UUID, settings: Settings
) -> tuple[BinaryIO, str]:
    row = authorize_photo_access(db, user_id, estimate_id)
    try:
        path = food_photo_storage_path(settings.food_photo_storage_root, row.storage_key)
        handle = path.open("rb")
    except OSError as error:
        raise FoodPhotoError("FOOD_PHOTO_STORAGE_UNAVAILABLE") from error
    audit_security_event(
        db,
        actor_user_id=user_id,
        owner_user_id=user_id,
        event_type="food_photo_accessed",
        resource_type="food_photo_estimate",
        resource_id=row.id,
    )
    db.commit()
    return handle, row.content_type
