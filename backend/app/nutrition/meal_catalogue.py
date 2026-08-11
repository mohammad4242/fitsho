from __future__ import annotations

from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.nutrition.enums import FoodVerificationStatus, MealCategory, MealIngredientRole
from app.nutrition.food_catalogue import FoodCompositionValue, calculate_meal_totals
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

SEED_MEALS: tuple[dict[str, object], ...] = (
    {
        "category": MealCategory.BREAKFAST,
        "name_fa": "تخم‌مرغ نیمرو با نان و گوجه خردشده",
        "name_en": "Fried eggs with bread and chopped tomato",
        "items": (
            ("egg", "100", "50", "200", True, MealIngredientRole.PROTEIN),
            ("sangak-bread", "60", "30", "120", True, MealIngredientRole.CARBOHYDRATE),
            ("tomato", "80", "30", "150", False, MealIngredientRole.MICRONUTRIENT_SOURCE),
            ("vegetable-oil", "5", "2", "10", False, MealIngredientRole.FAT),
        ),
    },
    {
        "category": MealCategory.LUNCH,
        "name_fa": "گوشت گوسفند و برنج با سالاد شیرازی",
        "name_en": "Lamb and rice with Shirazi salad",
        "items": (
            ("lamb", "150", "80", "220", True, MealIngredientRole.PROTEIN),
            ("basmati-rice", "80", "50", "130", True, MealIngredientRole.CARBOHYDRATE),
            ("tomato", "60", "30", "120", True, MealIngredientRole.MICRONUTRIENT_SOURCE),
            ("cucumber", "60", "30", "120", True, MealIngredientRole.FIBRE),
            ("onion", "20", "10", "40", False, MealIngredientRole.MICRONUTRIENT_SOURCE),
        ),
    },
    {
        "category": MealCategory.POST_WORKOUT,
        "name_fa": "تخم‌مرغ آب‌پز و سیب‌زمینی تنوری",
        "name_en": "Boiled eggs with baked potato",
        "items": (
            ("egg", "100", "50", "200", True, MealIngredientRole.PROTEIN),
            ("potato", "250", "150", "400", True, MealIngredientRole.CARBOHYDRATE),
        ),
    },
    {
        "category": MealCategory.SNACK,
        "name_fa": "۵۰ گرم بادام‌زمینی",
        "name_en": "50 g peanuts",
        "items": (("peanuts", "50", "20", "80", True, MealIngredientRole.FAT),),
    },
    {
        "category": MealCategory.DINNER,
        "name_fa": "سینه مرغ و برنج با سبزیجات",
        "name_en": "Chicken breast and rice with vegetables",
        "items": (
            ("chicken-breast", "160", "100", "250", True, MealIngredientRole.PROTEIN),
            ("basmati-rice", "80", "50", "130", True, MealIngredientRole.CARBOHYDRATE),
            ("broccoli", "75", "30", "150", False, MealIngredientRole.FIBRE),
            ("carrot", "75", "30", "150", False, MealIngredientRole.MICRONUTRIENT_SOURCE),
        ),
    },
)


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
        .order_by(NutritionCatalogueMeal.category, NutritionCatalogueMeal.name_en)
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
    meal = NutritionCatalogueMeal()
    db.add(meal)
    return _save_catalogue_meal(db, meal, payload)


def update_catalogue_meal(
    db: Session, meal_id: UUID, payload: CatalogueMealWrite
) -> NutritionCatalogueMeal | None:
    meal = db.get(NutritionCatalogueMeal, meal_id)
    if meal is None:
        return None
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
        name_fa=meal.name_fa,
        name_en=meal.name_en,
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
    seeded: list[NutritionCatalogueMeal] = []
    for seed in SEED_MEALS:
        category = seed["category"]
        assert isinstance(category, MealCategory)
        meal_id = uuid5(NAMESPACE_URL, f"fitsho:nutrition:meal:{category.value}:initial")
        meal = db.get(NutritionCatalogueMeal, meal_id)
        if meal is None:
            meal = NutritionCatalogueMeal(id=meal_id)
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
                id=uuid5(NAMESPACE_URL, f"fitsho:nutrition:meal:{category.value}:{slug}"),
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
