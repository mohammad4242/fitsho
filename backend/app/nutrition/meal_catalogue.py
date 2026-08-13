from __future__ import annotations

from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.nutrition.enums import FoodVerificationStatus, MealCategory
from app.nutrition.food_catalogue import FoodCompositionValue, calculate_meal_totals
from app.nutrition.meal_catalogue_seed_data import SEED_MEALS
from app.nutrition.models import (
    NutritionCatalogueFood,
    NutritionCatalogueMeal,
    NutritionCatalogueMealItem,
)
from app.nutrition.schemas import (
    CatalogueMealItemResponse,
    CatalogueMealResponse,
    CatalogueMealWrite,
)

CATEGORY_ORDER = tuple(MealCategory)


def list_catalogue_meals(
    db: Session, category: MealCategory | None = None
) -> list[NutritionCatalogueMeal]:
    query = (
        select(NutritionCatalogueMeal)
        .options(
            selectinload(NutritionCatalogueMeal.items)
            .selectinload(NutritionCatalogueMealItem.food)
            .selectinload(NutritionCatalogueFood.compositions)
        )
        .order_by(NutritionCatalogueMeal.category, NutritionCatalogueMeal.code)
    )
    if category is not None:
        query = query.where(NutritionCatalogueMeal.category == category)
    return list(db.scalars(query).unique())


def get_catalogue_meal(db: Session, meal_id: UUID) -> NutritionCatalogueMeal | None:
    return db.scalar(
        select(NutritionCatalogueMeal)
        .where(NutritionCatalogueMeal.id == meal_id)
        .options(
            selectinload(NutritionCatalogueMeal.items)
            .selectinload(NutritionCatalogueMealItem.food)
            .selectinload(NutritionCatalogueFood.compositions)
        )
    )


def create_catalogue_meal(db: Session, payload: CatalogueMealWrite) -> NutritionCatalogueMeal:
    if db.scalar(
        select(NutritionCatalogueMeal.id).where(NutritionCatalogueMeal.code == payload.code)
    ):
        raise ValueError("Meal code already exists")
    meal = NutritionCatalogueMeal(code=payload.code)
    return _save_catalogue_meal(db, meal, payload)


def update_catalogue_meal(
    db: Session, meal_id: UUID, payload: CatalogueMealWrite
) -> NutritionCatalogueMeal | None:
    meal = db.get(NutritionCatalogueMeal, meal_id)
    if meal is None:
        return None
    if meal.code != payload.code:
        raise ValueError("Meal code cannot be changed")
    meal.items.clear()
    db.flush()
    return _save_catalogue_meal(db, meal, payload)


def _save_catalogue_meal(
    db: Session, meal: NutritionCatalogueMeal, payload: CatalogueMealWrite
) -> NutritionCatalogueMeal:
    foods = {
        food.id: food
        for food in db.scalars(
            select(NutritionCatalogueFood).where(
                NutritionCatalogueFood.id.in_(item.food_id for item in payload.items)
            )
        )
    }
    if len(foods) != len(payload.items):
        raise ValueError("Every meal food must exist")
    if payload.verification_status == FoodVerificationStatus.VERIFIED.value and any(
        food.verification_status is not FoodVerificationStatus.VERIFIED for food in foods.values()
    ):
        raise ValueError("Verified meals may only use verified foods")
    meal.name_fa = payload.name_fa
    meal.name_en = payload.name_en
    meal.category = payload.category
    meal.verification_status = FoodVerificationStatus(payload.verification_status)
    meal.items = [
        NutritionCatalogueMealItem(
            food_id=item.food_id,
            reference_grams=item.reference_grams,
            min_grams=item.min_grams,
            max_grams=item.max_grams,
            is_required=item.is_required,
            functional_role=item.functional_role,
        )
        for item in payload.items
    ]
    db.add(meal)
    db.commit()
    saved = get_catalogue_meal(db, meal.id)
    if saved is None:
        raise ValueError("Meal was not found after saving")
    return saved


def meal_response(meal: NutritionCatalogueMeal) -> CatalogueMealResponse:
    totals = calculate_meal_totals(
        [
            (
                item.reference_grams,
                [
                    FoodCompositionValue(row.nutrient_code, row.value_per_100g, row.unit)
                    for row in item.food.compositions
                ],
            )
            for item in meal.items
        ]
    )
    return CatalogueMealResponse(
        id=meal.id,
        code=meal.code,
        name_fa=meal.name_fa,
        name_en=meal.name_en,
        image_url=meal.image_path,
        category=meal.category,
        verification_status=meal.verification_status.value,
        items=[
            CatalogueMealItemResponse(
                food_id=item.food_id,
                food_slug=item.food.slug,
                food_name_fa=item.food.name_fa,
                food_name_en=item.food.name_en,
                reference_grams=float(item.reference_grams),
                min_grams=float(item.min_grams),
                max_grams=float(item.max_grams),
                is_required=item.is_required,
                functional_role=item.functional_role,
            )
            for item in meal.items
        ],
        totals={key: float(value) if value is not None else None for key, value in totals.items()},
    )


def seed_meal_catalogue(db: Session, *, commit: bool = True) -> list[NutritionCatalogueMeal]:
    foods = {food.slug: food for food in db.scalars(select(NutritionCatalogueFood))}
    seed_codes = [str(seed["code"]) for seed in SEED_MEALS]
    existing_by_code = {
        meal.code: meal
        for meal in db.scalars(
            select(NutritionCatalogueMeal).where(NutritionCatalogueMeal.code.in_(seed_codes))
        )
    }
    seeded: list[NutritionCatalogueMeal] = []
    for seed in SEED_MEALS:
        category = seed["category"]
        assert isinstance(category, MealCategory)
        code = str(seed["code"])
        meal = existing_by_code.get(code)
        if meal is None:
            meal = NutritionCatalogueMeal(
                id=uuid5(NAMESPACE_URL, f"fitsho:nutrition:meal:{code}"), code=code
            )
            db.add(meal)
        else:
            meal.items.clear()
            db.flush()
        item_seeds = seed["items"]
        assert isinstance(item_seeds, tuple)
        missing = [slug for slug, *_ in item_seeds if slug not in foods]
        if missing:
            raise ValueError(f"Meal seed foods are missing: {', '.join(missing)}")
        meal.name_fa = str(seed["name_fa"])
        meal.name_en = str(seed["name_en"])
        meal.code = code
        meal.category = category
        meal.verification_status = (
            FoodVerificationStatus.VERIFIED
            if all(
                foods[slug].verification_status is FoodVerificationStatus.VERIFIED
                for slug, *_ in item_seeds
            )
            else FoodVerificationStatus.DRAFT
        )
        meal.items = [
            NutritionCatalogueMealItem(
                id=uuid5(NAMESPACE_URL, f"fitsho:nutrition:meal:{code}:{slug}"),
                food_id=foods[slug].id,
                reference_grams=Decimal(reference),
                min_grams=Decimal(minimum),
                max_grams=Decimal(maximum),
                is_required=required,
                functional_role=role,
            )
            for slug, reference, minimum, maximum, required, role in item_seeds
        ]
        seeded.append(meal)
    if commit:
        db.commit()
    else:
        db.flush()
    return list_catalogue_meals(db)
