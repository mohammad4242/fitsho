from __future__ import annotations

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
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.ai.task_provider import build_task_provider
from app.body_analysis.admin_config.enums import AIExecutionBackend, AITaskType
from app.body_analysis.admin_config.models import AITaskConfig
from app.body_analysis.admin_config.service import AIConfigError, decrypted_key
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
    calories: float = Field(ge=0, le=10000)
    protein_g: float = Field(ge=0, le=1000)
    carbohydrate_g: float = Field(ge=0, le=1000)
    fat_g: float = Field(ge=0, le=1000)

    @model_validator(mode="before")
    @classmethod
    def _fill_and_calculate_macros(cls, data: object) -> object:
        if isinstance(data, dict):
            p = float(data.get("protein_g") or 0.0)
            c = float(data.get("carbohydrate_g") or 0.0)
            f = float(data.get("fat_g") or 0.0)
            cal = float(data.get("calories") or 0.0)
            if cal <= 0 and (p > 0 or c > 0 or f > 0):
                data["calories"] = round(p * 4.0 + c * 4.0 + f * 9.0, 1)
            elif "calories" not in data:
                data["calories"] = round(p * 4.0 + c * 4.0 + f * 9.0, 1)
            if "protein_g" not in data:
                data["protein_g"] = 0.0
            if "carbohydrate_g" not in data:
                data["carbohydrate_g"] = 0.0
            if "fat_g" not in data:
                data["fat_g"] = 0.0
        return data


class FoodPhotoOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meal_name_guess: str | None = Field(default=None, max_length=160)
    items: list[EstimatedPhotoItem] = Field(min_length=1, max_length=20)
    overall_confidence: float = Field(ge=0, le=1)
    needs_user_confirmation: bool


RESPONSE_SCHEMA = FoodPhotoOutput.model_json_schema()


def build_food_photo_request(
    *,
    primary_model: str,
    fallback_models: tuple[str, ...],
    provider_preferences: ProviderRoutingPreferences,
    temperature: float,
    max_output_tokens: int,
    language: str = "fa",
) -> StructuredGenerationRequest:
    """Build the one production food-photo task request for any provider."""
    is_fa = language.lower().startswith("fa")
    if is_fa:
        system_prompt = (
            "تو دستیار هوشمند و متخصص تحلیل تصاویر غذا و تغذیه هستی. "
            "وظیفه تو شناسایی دقیق تمام اجزای خوراکی بشقاب و برآورد مقدار و ارزش غذایی آن‌هاست.\n\n"
            "قوانین اجباری:\n"
            "۱. زبان نام‌گذاری: تمام نام‌ها (فیلد name_guess برای هر جزء و فیلد meal_name_guess "
            "برای کل وعده) باید حتماً به زبان فارسی روان، متداول، امروزی و کوتاه باشد. "
            "از به کار بردن کلمات انگلیسی یا توضیحات طولانی و کتابی در نام غذا اکیداً خودداری کن "
            "(مثال‌های درست: 'جوجه کباب'، 'کباب کوبیده'، 'برنج زعفرانی'، 'گوجه کبابی'، "
            "'پیاز کبابی'، 'سالاد شیرازی'، 'سبزی خوردن'). "
            "توضیحات و شواهد دیداری را در visible_evidence بنویس.\n"
            "۲. مقدار و واحد: مقدار تخمینی هر جزء (estimated_amount) را به گرم تخمین بزن "
            "و فیلد unit را حتماً 'g' قرار بده.\n"
            "۳. محاسبه کالری و ماکروها: برای هر جزء، بر اساس وزن تخمینی آن، مقادیر دقیق "
            "protein_g، carbohydrate_g، fat_g و همچنین calories (کل انرژی به کیلوکالری) "
            "را محاسبه کن. فرمول اساسی محاسبه کالری: "
            "calories = (protein_g × 4) + (carbohydrate_g × 4) + (fat_g × 9). "
            "فیلد calories برای هر غذایی که کالری دارد باید حتماً بیشتر از صفر باشد "
            "و هرگز نباید ۰ ثبت شود.\n"
            "۴. شواهد دیداری و عدم قطعیت‌ها را بنویس. ادعای پزشکی یا آلرژی ارائه نده."
        )
        instruction = (
            "این تصویر غذا را بدون اطلاعات شخصی تحلیل کن و خروجی را با نام‌های فارسی روان "
            "و روزمره ارائه بده."
        )
    else:
        system_prompt = (
            "You are an expert food image recognition and nutrition assistant. "
            "Identify all visible food items and estimate their portions and nutritional value.\n\n"
            "Mandatory rules:\n"
            "1. Language & Naming: All food names ('name_guess') and the overall meal name "
            "('meal_name_guess') must be in natural, concise, everyday English "
            "(e.g. 'Chicken Kebab', 'Ground Beef Kebab', 'Saffron Rice', 'Grilled Tomato', "
            "'Grilled Onion', 'Fresh Herbs'). Keep names concise; "
            "put detailed observations in visible_evidence.\n"
            "2. Portions & Units: Estimate the portion of each item in grams ('estimated_amount') "
            "and set unit to 'g'.\n"
            "3. Calories & Macronutrients: Calculate estimated calories ('calories' in kcal), "
            "protein_g, carbohydrate_g, and fat_g based on the estimated portion. "
            "Standard Atwater formula: "
            "calories = (4 * protein_g) + (4 * carbohydrate_g) + (9 * fat_g). "
            "4. Note visible evidence and uncertainties. "
            "Do not provide medical advice or allergy claims."
        )
        instruction = (
            "Analyze this food image without personal data and provide nutritional estimates."
        )

    return StructuredGenerationRequest(
        system_prompt=system_prompt,
        input_payload={"instruction": instruction},
        response_schema=RESPONSE_SCHEMA,
        schema_name="fitsho_food_photo_estimate_v1",
        route=ModelRoute(primary_model=primary_model, fallback_models=fallback_models),
        provider_preferences=provider_preferences,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )


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
    return photo_response(previous, db=db) if previous is not None else None


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
    try:
        os.chmod(destination.parent, 0o755)
    except OSError:
        pass
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o644)
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
    agent_http_client: httpx.AsyncClient | None = None,
    language: str = "fa",
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
    if config is None or not config.enabled:
        raise FoodPhotoError("FOOD_PHOTO_ESTIMATION_DISABLED")
    try:
        backend = AIExecutionBackend(config.execution_backend)
        selected_client = client if backend is AIExecutionBackend.API else agent_http_client
        if not isinstance(selected_client, httpx.AsyncClient):
            raise ValueError("AI HTTP client is unavailable")
        key = (
            decrypted_key(db, provider=config.provider, settings=settings)
            if backend is AIExecutionBackend.API
            else None
        )
        configured = build_task_provider(
            config,
            settings=settings,
            http_client=selected_client,
            agent_http_client=(
                selected_client if backend is AIExecutionBackend.AGENT_SERVICE else None
            ),
            api_key=key,
        )
    except (AIConfigError, ValueError) as error:
        raise FoodPhotoError("FOOD_PHOTO_PROVIDER_UNAVAILABLE") from error
    content = await file.read(settings.food_photo_max_bytes + 1)
    if len(content) > settings.food_photo_max_bytes:
        raise FoodPhotoError("FOOD_PHOTO_TOO_LARGE")
    normalized, mime_type = _normalize_image(content, settings.food_photo_max_pixels)
    key = _store(settings.food_photo_storage_root, normalized)
    request = build_food_photo_request(
        primary_model=configured.primary_model_id,
        fallback_models=configured.fallback_model_ids,
        provider_preferences=configured.routing_preferences,
        temperature=config.temperature,
        max_output_tokens=config.max_output_tokens,
        language=language,
    )
    try:
        result = await configured.provider.analyze_images(
            request,
            images=(
                ImageInput(
                    label="food_photo",
                    mime_type="image/jpeg",
                    storage_scope="food",
                    storage_key=key,
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
            provider=configured.provider_name,
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
        provider=configured.provider_name,
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
        metadata={"provider": configured.provider_name, "byte_size": len(normalized)},
    )
    record_operational_event(
        db,
        category="ai",
        event_name="food_photo_estimation",
        status="success",
        provider=configured.provider_name,
        counters={
            "requests": 1,
            "errors": 0,
            "input_tokens": result.input_tokens or 0,
            "output_tokens": result.output_tokens or 0,
        },
    )
    db.commit()
    db.refresh(row)
    return photo_response(row, db=db)


def _item_float(item: dict[str, object], key: str, default: float = 0.0) -> float:
    val = item.get(key)
    if val is None:
        return default
    try:
        return float(str(val))
    except (ValueError, TypeError):
        return default


def _item_is_nutrition_ready(item: dict[str, object]) -> bool:
    """Return True iff this item can contribute to the nutrition summary."""
    has_catalogue = bool(item.get("food_id")) and item.get("unit") == "g"
    has_ai_macros = item.get("calories") is not None and (
        _item_float(item, "calories") > 0
        or _item_float(item, "protein_g") > 0
        or _item_float(item, "carbohydrate_g") > 0
        or _item_float(item, "fat_g") > 0
    )
    return has_catalogue or has_ai_macros


def _calculate_photo_macro_totals(
    db: Session, items: list[dict[str, object]]
) -> tuple[dict[str, float], bool]:
    """Calculate nutrition totals from mapped_items (catalogue or direct AI).

    Uses batched catalogue queries for items linked to the catalogue,
    and direct AI-estimated macros for items without a catalogue link.
    """
    nutrient_keys = {
        "energy_kcal": "calories",
        "protein_g": "protein_g",
        "carbohydrate_g": "carbohydrate_g",
        "total_fat_g": "fat_g",
    }
    totals: dict[str, Decimal] = {
        "calories": Decimal(),
        "protein_g": Decimal(),
        "carbohydrate_g": Decimal(),
        "fat_g": Decimal(),
    }

    catalogue_items: list[tuple[dict[str, object], UUID]] = []
    direct_items: list[dict[str, object]] = []
    not_ready_count = 0

    for item in items:
        if bool(item.get("food_id")) and item.get("unit") == "g":
            catalogue_items.append((item, UUID(str(item["food_id"]))))
        elif _item_is_nutrition_ready(item):
            direct_items.append(item)
        else:
            not_ready_count += 1

    if catalogue_items:
        food_ids = [fid for _, fid in catalogue_items]
        foods_with_compositions = db.scalars(
            select(NutritionCatalogueFood)
            .where(
                NutritionCatalogueFood.id.in_(food_ids),
                NutritionCatalogueFood.verification_status == FoodVerificationStatus.VERIFIED,
            )
            .options(selectinload(NutritionCatalogueFood.compositions))
        ).all()
        food_map = {food.id: food for food in foods_with_compositions}

        for item, food_id in catalogue_items:
            food = food_map.get(food_id)
            if food is None:
                # If food verification expired, fall back to direct item macros if present
                if _item_is_nutrition_ready(item):
                    direct_items.append(item)
                else:
                    not_ready_count += 1
                continue
            factor = Decimal(str(item["estimated_amount"])) / Decimal("100")
            for composition in food.compositions:
                output_key = nutrient_keys.get(composition.nutrient_code)
                if output_key is not None:
                    totals[output_key] += composition.value_per_100g * factor

    for item in direct_items:
        cal = _item_float(item, "calories")
        prot = _item_float(item, "protein_g")
        carb = _item_float(item, "carbohydrate_g")
        fat = _item_float(item, "fat_g")
        if cal <= 0 and (prot > 0 or carb > 0 or fat > 0):
            cal = round(prot * 4.0 + carb * 4.0 + fat * 9.0, 1)
            item["calories"] = cal
        totals["calories"] += Decimal(str(round(cal, 2)))
        totals["protein_g"] += Decimal(str(round(prot, 2)))
        totals["carbohydrate_g"] += Decimal(str(round(carb, 2)))
        totals["fat_g"] += Decimal(str(round(fat, 2)))

    complete = len(items) > 0 and not_ready_count == 0

    return {key: float(value) for key, value in totals.items()}, complete


def photo_response(
    row: NutritionFoodPhotoEstimate, *, db: Session | None = None
) -> dict[str, object]:
    items: list[dict[str, object]] = []
    for index, item in enumerate(row.mapped_items):
        cal = _item_float(item, "calories", 0.0)
        prot = _item_float(item, "protein_g", 0.0)
        carb = _item_float(item, "carbohydrate_g", 0.0)
        fat = _item_float(item, "fat_g", 0.0)
        if cal <= 0 and (prot > 0 or carb > 0 or fat > 0):
            cal = round(prot * 4.0 + carb * 4.0 + fat * 9.0, 1)
        items.append(
            {
                **item,
                "item_id": item.get("item_id") or f"legacy-{index}",
                "calories": cal,
                "protein_g": prot,
                "carbohydrate_g": carb,
                "fat_g": fat,
            }
        )
    macro_totals: dict[str, float] = {
        "calories": 0.0,
        "protein_g": 0.0,
        "carbohydrate_g": 0.0,
        "fat_g": 0.0,
    }
    macro_totals_complete = False
    if db is not None:
        macro_totals, macro_totals_complete = _calculate_photo_macro_totals(
            db, list(row.mapped_items)
        )
    return {
        "id": row.id,
        "status": row.status,
        "items": items,
        "overall_confidence": row.raw_estimate.get("overall_confidence"),
        "needs_user_confirmation": True,
        "model_id": row.model_id,
        "expires_at": row.expires_at,
        "macro_totals": macro_totals,
        "macro_totals_complete": macro_totals_complete,
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
            old_amount = _item_float(item, "estimated_amount", 1.0)
            new_amount = float(estimated_amount)
            if old_amount > 0 and new_amount > 0:
                ratio = new_amount / old_amount
                for key in ("calories", "protein_g", "carbohydrate_g", "fat_g"):
                    if key in item and item[key] is not None:
                        item[key] = round(_item_float(item, key) * ratio, 2)
            item["estimated_amount"] = new_amount
        if food_id is not None:
            food = db.scalar(
                select(NutritionCatalogueFood).where(
                    NutritionCatalogueFood.id == food_id,
                    NutritionCatalogueFood.verification_status == FoodVerificationStatus.VERIFIED,
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
    return photo_response(row, db=db)


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
    if not row.mapped_items:
        raise FoodPhotoError("UNRESOLVED_ITEMS_REQUIRE_EDIT")
    for item in row.mapped_items:
        if not _item_is_nutrition_ready(item):
            raise FoodPhotoError("UNRESOLVED_ITEMS_REQUIRE_EDIT")

    catalogue_food_ids = [
        UUID(str(item["food_id"]))
        for item in row.mapped_items
        if bool(item.get("food_id")) and item.get("unit") == "g"
    ]
    food_map: dict[UUID, NutritionCatalogueFood] = {}
    if catalogue_food_ids:
        foods_with_compositions = db.scalars(
            select(NutritionCatalogueFood)
            .where(
                NutritionCatalogueFood.id.in_(catalogue_food_ids),
                NutritionCatalogueFood.verification_status == FoodVerificationStatus.VERIFIED,
            )
            .options(selectinload(NutritionCatalogueFood.compositions))
        ).all()
        food_map = {food.id: food for food in foods_with_compositions}
        if len(food_map) != len(catalogue_food_ids):
            raise FoodPhotoError("UNRESOLVED_ITEMS_REQUIRE_EDIT")

    created: list[NutritionConsumptionEntry] = []
    for item in row.mapped_items:
        fid = UUID(str(item["food_id"])) if item.get("food_id") else None
        food = food_map.get(fid) if fid else None
        grams = _item_float(item, "estimated_amount", 100.0)

        if food is not None:
            nutrients = {
                composition.nutrient_code: str(
                    composition.value_per_100g * (Decimal(str(grams)) / Decimal("100"))
                )
                for composition in food.compositions
            }
            warning_codes = list(
                dict.fromkeys(
                    ["PHOTO_ESTIMATE_APPROXIMATE", *actual_intake_warnings(db, user_id, food)]
                )
            )
            display_name = food.name_fa
            entry_food_id: UUID | None = food.id
        else:
            p = _item_float(item, "protein_g", 0.0)
            c = _item_float(item, "carbohydrate_g", 0.0)
            f = _item_float(item, "fat_g", 0.0)
            cal = _item_float(item, "calories", 0.0)
            if cal <= 0 and (p > 0 or c > 0 or f > 0):
                cal = round(p * 4.0 + c * 4.0 + f * 9.0, 1)
            nutrients = {
                "energy_kcal": str(round(cal, 2)),
                "protein_g": str(round(p, 2)),
                "carbohydrate_g": str(round(c, 2)),
                "total_fat_g": str(round(f, 2)),
            }
            warning_codes = ["PHOTO_ESTIMATE_APPROXIMATE"]
            display_name = str(item.get("name_guess", "غذای تخمینی"))
            entry_food_id = None

        entry = NutritionConsumptionEntry(
            user_id=user_id,
            entry_date=entry_date,
            food_id=entry_food_id,
            display_name=display_name,
            quantity_grams=Decimal(str(grams)) if item.get("unit") == "g" else None,
            source=NutritionConsumptionSource.PHOTO_ESTIMATED_CONFIRMED,
            confidence=EstimateConfidence.LOW,
            user_confirmed=True,
            nutrients=nutrients,
            warning_codes=warning_codes,
        )
        db.add(entry)
        created.append(entry)

    row.status = "confirmed"
    row.confirmed_at = datetime.now(UTC)
    db.commit()
    return [{"id": item.id, "display_name": item.display_name} for item in created]


def confirm_photo_macro_preview(db: Session, user_id: UUID, estimate_id: UUID) -> dict[str, float]:
    row = db.scalar(
        select(NutritionFoodPhotoEstimate).where(
            NutritionFoodPhotoEstimate.id == estimate_id,
            NutritionFoodPhotoEstimate.user_id == user_id,
            NutritionFoodPhotoEstimate.status == "estimated",
        )
    )
    if row is None:
        raise FoodPhotoError("FOOD_PHOTO_ESTIMATE_NOT_FOUND")
    # Validate: all items must be nutrition-ready before confirming.
    if not row.mapped_items:
        raise FoodPhotoError("UNRESOLVED_ITEMS_REQUIRE_EDIT")
    for item in row.mapped_items:
        if not _item_is_nutrition_ready(item):
            raise FoodPhotoError("UNRESOLVED_ITEMS_REQUIRE_EDIT")
    totals, complete = _calculate_photo_macro_totals(db, list(row.mapped_items))
    if not complete:
        raise FoodPhotoError("UNRESOLVED_ITEMS_REQUIRE_EDIT")
    row.status = "confirmed"
    row.confirmed_at = datetime.now(UTC)
    db.commit()
    return totals


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
