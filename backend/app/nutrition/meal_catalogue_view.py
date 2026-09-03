"""Member-facing meal catalogue read model."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.nutrition.enums import FoodVerificationStatus, MealCategory
from app.nutrition.meal_catalogue import CATEGORY_ORDER
from app.nutrition.models import NutritionCatalogueMeal
from app.nutrition.schemas import (
    MemberCatalogueMealPageResponse,
    MemberCatalogueMealResponse,
)


def member_meal_catalogue(
    db: Session,
    *,
    category: MealCategory | None = None,
) -> MemberCatalogueMealPageResponse:
    query = (
        select(NutritionCatalogueMeal)
        .where(NutritionCatalogueMeal.verification_status == FoodVerificationStatus.VERIFIED)
        .order_by(NutritionCatalogueMeal.category, NutritionCatalogueMeal.code)
    )
    if category is not None:
        query = query.where(NutritionCatalogueMeal.category == category)

    meals = list(db.scalars(query).all())
    return MemberCatalogueMealPageResponse(
        items=[
            MemberCatalogueMealResponse(
                id=meal.id,
                name_fa=meal.name_fa,
                name_en=meal.name_en,
                image_url=meal.image_path,
                category=meal.category,
            )
            for meal in meals
        ],
        categories=list(CATEGORY_ORDER),
    )
