from app.nutrition.enums import MainMealCountBucket, SnackCountBucket
from app.nutrition.schemas import NutritionProfileInput


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
