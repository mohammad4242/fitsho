from sqlalchemy import select
from sqlalchemy.orm import Session

from app.nutrition.enums import FoodItemKind, MainMealCountBucket, SnackCountBucket
from app.nutrition.food_catalogue import seed_base_iranian_food_catalogue
from app.nutrition.models import NutritionFoodItem, NutritionProfile
from app.nutrition.schemas import NutritionProfileInput
from app.nutrition.service import save_nutrition_profile
from tests.nutrition.test_nutrition_api import create_shared_and_safety


def profile_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "daily_activity_level": "moderate",
        "individual_monthly_food_budget_irr": 13_000_000,
        "budget_style": "strict",
        "main_meal_count_bucket": "four_or_more_main_meals",
        "snack_count_bucket": "three_or_more_snacks",
        "preferred_plan_start_day": "saturday",
        "dietary_pattern": "omnivore",
        "allergies": [],
        "intolerances": [],
        "religious_cultural_exclusions": [],
        "daily_check_in_enabled": False,
    }
    payload.update(overrides)
    return payload


def test_meal_buckets_resolve_to_effective_planner_slots() -> None:
    profile = NutritionProfileInput(**profile_payload())

    assert profile.main_meal_count_bucket is MainMealCountBucket.FOUR_OR_MORE
    assert profile.snack_count_bucket is SnackCountBucket.THREE_OR_MORE
    assert profile.meals_per_day == 4
    assert profile.snacks_per_day == 3


def test_legacy_numeric_meal_inputs_are_accepted_without_cooking_requirements() -> None:
    profile = NutritionProfileInput(
        **profile_payload(
            main_meal_count_bucket=None,
            snack_count_bucket=None,
            meals_per_day=2,
            snacks_per_day=0,
        )
    )

    assert profile.main_meal_count_bucket is MainMealCountBucket.TWO
    assert profile.snack_count_bucket is SnackCountBucket.ZERO
    assert profile.meals_per_day == 2
    assert profile.snacks_per_day == 0
    assert profile.cooking_skill.value == "none"
    assert profile.cooking_frequency_per_week == 0


def test_legacy_cooking_values_do_not_rewrite_existing_profile(client, db: Session) -> None:
    user_id = create_shared_and_safety(client, "legacy-cooking-ignored@example.com")
    first = NutritionProfileInput(**profile_payload())
    save_nutrition_profile(db, user_id, first)
    profile = db.get(NutritionProfile, user_id)
    assert profile is not None
    profile.maximum_cooking_time_minutes = 17
    profile.cooking_frequency_per_week = 2
    db.commit()

    save_nutrition_profile(
        db,
        user_id,
        NutritionProfileInput(
            **profile_payload(maximum_cooking_time_minutes=240, cooking_frequency_per_week=7)
        ),
    )

    db.refresh(profile)
    assert profile.maximum_cooking_time_minutes == 17
    assert profile.cooking_frequency_per_week == 2


def test_ordinary_preferences_resolve_only_exact_canonical_food_aliases(
    client,
    db: Session,
) -> None:
    user_id = create_shared_and_safety(client, "resolved-preferences@example.com")
    foods = seed_base_iranian_food_catalogue(db, commit=False)
    chicken = next(food for food in foods if food.slug == "chicken-breast")

    save_nutrition_profile(
        db,
        user_id,
        NutritionProfileInput(
            **profile_payload(
                favourite_foods=["فیله مرغ", "ترکیب ناشناخته"],
                disliked_foods=["سینه مرغ"],
            )
        ),
    )

    items = db.scalars(
        select(NutritionFoodItem)
        .where(
            NutritionFoodItem.user_id == user_id,
            NutritionFoodItem.kind.in_([FoodItemKind.FAVOURITE, FoodItemKind.DISLIKED]),
        )
        .order_by(NutritionFoodItem.name)
    ).all()
    resolved = {item.name: getattr(item, "catalogue_food_id", None) for item in items}
    assert resolved == {
        "ترکیب ناشناخته": None,
        "سینه مرغ": chicken.id,
        "فیله مرغ": chicken.id,
    }
