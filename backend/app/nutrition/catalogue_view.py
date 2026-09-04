"""Member-facing catalogue read model."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.nutrition.enums import FoodVerificationStatus
from app.nutrition.food_catalogue import REQUIRED_PRIMARY_NUTRIENTS, normalize_food_alias
from app.nutrition.models import NutritionCatalogueFood
from app.nutrition.price_overrides import EffectivePrice, effective_prices
from app.nutrition.schemas import (
    AdminFoodCatalogueItemResponse,
    AdminFoodCataloguePageResponse,
    FoodCatalogueItemResponse,
    FoodCatalogueNutrientBasis,
    FoodCataloguePageResponse,
    FoodCataloguePriceResponse,
    FoodCatalogueSourceResponse,
)

PRIMARY_NUTRIENTS = tuple(sorted(REQUIRED_PRIMARY_NUTRIENTS))
TOMAN_TO_IRR = Decimal("10")


def _irr_reference_unit(canonical_unit: str) -> str:
    return canonical_unit.replace("TOMAN_", "IRR_", 1)


def member_food_catalogue(
    db: Session,
    *,
    query: str | None,
    category: str | None,
    page: int,
    page_size: int,
) -> FoodCataloguePageResponse:
    page_data = _catalogue_page(db, query=query, category=category, page=page, page_size=page_size)
    return FoodCataloguePageResponse(
        items=[_member_item(food) for food in page_data.selected],
        **page_data.metadata,
    )


def admin_food_catalogue(
    db: Session,
    *,
    query: str | None,
    category: str | None,
    page: int,
    page_size: int,
) -> AdminFoodCataloguePageResponse:
    page_data = _catalogue_page(db, query=query, category=category, page=page, page_size=page_size)
    prices = effective_prices(db, [food.id for food in page_data.selected])
    return AdminFoodCataloguePageResponse(
        items=[_admin_item(food, prices.get(food.id)) for food in page_data.selected],
        **page_data.metadata,
    )


class _CataloguePage:
    def __init__(self, selected: list[NutritionCatalogueFood], metadata: dict[str, object]) -> None:
        self.selected = selected
        self.metadata = metadata


def _catalogue_page(
    db: Session, *, query: str | None, category: str | None, page: int, page_size: int
) -> _CataloguePage:
    foods = list(
        db.scalars(
            select(NutritionCatalogueFood)
            .where(NutritionCatalogueFood.verification_status == FoodVerificationStatus.VERIFIED)
            .options(
                selectinload(NutritionCatalogueFood.aliases),
                selectinload(NutritionCatalogueFood.compositions),
                selectinload(NutritionCatalogueFood.portions),
            )
            .order_by(NutritionCatalogueFood.name_fa, NutritionCatalogueFood.slug)
        ).all()
    )
    categories = sorted({food.category for food in foods})
    normalized_query = normalize_food_alias(query or "")
    if normalized_query:
        foods = [
            food
            for food in foods
            if normalized_query
            in " ".join(
                normalize_food_alias(value)
                for value in (food.name_fa, food.name_en, *(alias.alias for alias in food.aliases))
            )
        ]
    if category:
        foods = [food for food in foods if food.category == category]
    total = len(foods)
    start = (page - 1) * page_size
    selected = foods[start : start + page_size]
    return _CataloguePage(
        selected,
        {"page": page, "page_size": page_size, "total": total, "categories": categories},
    )


def _member_item(food: NutritionCatalogueFood) -> FoodCatalogueItemResponse:
    composition_by_code = {
        composition.nutrient_code: composition for composition in food.compositions
    }
    return FoodCatalogueItemResponse(
        id=food.id,
        slug=food.slug,
        name_fa=food.name_fa,
        name_en=food.name_en,
        image_url=food.image_path,
        category=food.category,
        measurement_basis=food.measurement_basis,
        nutrient_basis=FoodCatalogueNutrientBasis(
            quantity=food.canonical_quantity, unit=food.canonical_unit
        ),
        macros={
            code: composition_by_code[code].value_per_100g if code in composition_by_code else None
            for code in PRIMARY_NUTRIENTS
        },
        nutrients=[
            {
                "nutrient_code": item.nutrient_code,
                "value_per_100g": item.value_per_100g,
                "unit": item.unit,
                "unit_form": item.unit_form,
                "source_name": item.source_name,
                "source_reference": item.source_reference,
                "confidence": item.confidence,
            }
            for item in sorted(food.compositions, key=lambda item: item.nutrient_code)
        ],
        portions=[
            {
                "code": item.code,
                "quantity": item.quantity,
                "label_fa": item.label_fa,
                "label_en": item.label_en,
                "grams": item.grams,
                "is_default": item.is_default,
                "source_name": item.source_name,
                "source_reference": item.source_reference,
            }
            for item in food.portions
        ],
        source=FoodCatalogueSourceResponse(
            name=food.source_name,
            reference=food.source_reference,
            source_food_id=food.source_food_id,
            data_version=food.data_version,
            access_date=food.source_access_date,
        ),
        allergen_tags=list(food.allergen_tags or ()),
        allergen_metadata_verified=food.allergen_metadata_verified,
    )


def _admin_item(
    food: NutritionCatalogueFood, effective: EffectivePrice | None
) -> AdminFoodCatalogueItemResponse:
    price = FoodCataloguePriceResponse(status="not_found")
    if effective is not None:
        price = FoodCataloguePriceResponse(
            status="accepted",
            reference_price_irr=effective.reference_price_toman * TOMAN_TO_IRR,
            reference_unit=_irr_reference_unit(effective.canonical_unit),
            observed_at=effective.observed_at,
            reference_price_toman=effective.reference_price_toman,
            canonical_unit=effective.canonical_unit,
            accepted_at=effective.accepted_at,
            source=effective.source,
        )
    return AdminFoodCatalogueItemResponse(**_member_item(food).model_dump(), price=price)
