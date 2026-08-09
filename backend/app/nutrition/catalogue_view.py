"""Member-facing catalogue read model."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.nutrition.enums import FoodVerificationStatus
from app.nutrition.food_catalogue import REQUIRED_PRIMARY_NUTRIENTS, normalize_food_alias
from app.nutrition.models import NutritionCatalogueFood
from app.nutrition.price_overrides import effective_prices
from app.nutrition.schemas import (
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
    foods = list(
        db.scalars(
            select(NutritionCatalogueFood)
            .where(NutritionCatalogueFood.verification_status == FoodVerificationStatus.VERIFIED)
            .options(
                selectinload(NutritionCatalogueFood.aliases),
                selectinload(NutritionCatalogueFood.compositions),
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
    prices = effective_prices(db, [food.id for food in selected])
    items: list[FoodCatalogueItemResponse] = []
    for food in selected:
        composition_by_code = {
            composition.nutrient_code: composition for composition in food.compositions
        }
        effective = prices.get(food.id)
        price = (
            FoodCataloguePriceResponse(status="not_found")
            if effective is None
            else FoodCataloguePriceResponse(
                status="accepted",
                reference_price_irr=effective.reference_price_toman * TOMAN_TO_IRR,
                reference_unit=_irr_reference_unit(effective.canonical_unit),
                observed_at=effective.observed_at,
                reference_price_toman=effective.reference_price_toman,
                canonical_unit=effective.canonical_unit,
                accepted_at=effective.accepted_at,
                source=effective.source,
            )
        )
        items.append(
            FoodCatalogueItemResponse(
                id=food.id,
                slug=food.slug,
                name_fa=food.name_fa,
                name_en=food.name_en,
                category=food.category,
                measurement_basis=food.measurement_basis,
                nutrient_basis=FoodCatalogueNutrientBasis(
                    quantity=food.canonical_quantity,
                    unit=food.canonical_unit,
                ),
                price=price,
                macros={
                    code: (
                        composition_by_code[code].value_per_100g
                        if code in composition_by_code
                        else None
                    )
                    for code in PRIMARY_NUTRIENTS
                },
                nutrients=[
                    {
                        "nutrient_code": composition.nutrient_code,
                        "value_per_100g": composition.value_per_100g,
                        "unit": composition.unit,
                        "unit_form": composition.unit_form,
                        "source_name": composition.source_name,
                        "source_reference": composition.source_reference,
                        "confidence": composition.confidence,
                    }
                    for composition in sorted(
                        food.compositions, key=lambda item: item.nutrient_code
                    )
                ],
                source=FoodCatalogueSourceResponse(
                    name=food.source_name,
                    reference=food.source_reference,
                    source_food_id=food.source_food_id,
                    data_version=food.data_version,
                    access_date=food.source_access_date,
                ),
            )
        )
    return FoodCataloguePageResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        categories=categories,
    )
