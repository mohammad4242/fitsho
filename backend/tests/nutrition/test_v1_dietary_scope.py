from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.nutrition.enums import DietaryPattern
from app.nutrition.models import NutritionProfile
from tests.nutrition.test_weekly_plan_api import ORIGIN, _birth_date


def _setup_user_with_safety(client: TestClient, email: str) -> None:
    res = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "securepassword123"},
    )
    assert res.status_code == 201
    assert (
        client.post(
            "/api/v1/profile/mode", headers=ORIGIN, json={"product_mode": "nutrition"}
        ).status_code
        == 201
    )
    assert (
        client.put(
            "/api/v1/profile/shared",
            headers=ORIGIN,
            json={
                "display_name": "تست گیاه‌خوار",
                "birth_date": _birth_date(),
                "sex": "female",
                "height_cm": 165,
                "current_weight_kg": 60.0,
                "fitness_goal": "maintain_weight",
            },
        ).status_code
        == 200
    )
    assert (
        client.put(
            "/api/v1/nutrition/safety",
            headers=ORIGIN,
            json={
                "conditions": [],
                "medications": [],
                "dangerous_food_reaction_history": False,
                "pregnant": False,
                "breastfeeding": False,
                "eating_disorder_diagnosed": False,
                "eating_disorder_active_symptoms": False,
                "emergency_or_danger_symptoms": False,
                "physician_dietary_restrictions": None,
                "other_relevant_condition": None,
            },
        ).status_code
        == 200
    )


def test_put_profile_rejects_vegetarian_with_422(client: TestClient) -> None:
    _setup_user_with_safety(client, "veg-test-1@example.com")
    response = client.put(
        "/api/v1/nutrition/profile",
        headers=ORIGIN,
        json={
            "daily_activity_level": "moderate",
            "individual_monthly_food_budget_irr": 100_000_000,
            "budget_style": "strict",
            "meals_per_day": 3,
            "snacks_per_day": 1,
            "preferred_plan_start_day": "saturday",
            "plan_style": "balanced",
            "cooking_skill": "basic",
            "maximum_cooking_time_minutes": 45,
            "cooking_frequency_per_week": 4,
            "meal_preparation_preference": "mixed",
            "refrigerator_access": True,
            "freezer_access": True,
            "cooking_equipment": ["stove"],
            "supplied_meals_per_week": 0,
            "supplied_meal_source": None,
            "foods_available_at_home": [],
            "favourite_foods": [],
            "disliked_foods": [],
            "never_suggest_foods": [],
            "refused_foods": [],
            "allergies": [],
            "intolerances": [],
            "dietary_pattern": "vegetarian",
            "religious_cultural_exclusions": [],
            "preferred_variety": "medium",
            "maximum_meal_repetition_per_week": 2,
            "accepts_leftovers": True,
            "accepts_batch_cooking": True,
            "work_shift_context": None,
            "daily_check_in_enabled": False,
            "preferred_check_in_time": None,
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["detail"]["code"] == "DIETARY_PATTERN_NOT_SUPPORTED_V1"


def test_put_profile_rejects_vegan_with_422(client: TestClient) -> None:
    _setup_user_with_safety(client, "vegan-test-1@example.com")
    response = client.put(
        "/api/v1/nutrition/profile",
        headers=ORIGIN,
        json={
            "daily_activity_level": "moderate",
            "individual_monthly_food_budget_irr": 100_000_000,
            "budget_style": "strict",
            "meals_per_day": 3,
            "snacks_per_day": 1,
            "preferred_plan_start_day": "saturday",
            "plan_style": "balanced",
            "cooking_skill": "basic",
            "maximum_cooking_time_minutes": 45,
            "cooking_frequency_per_week": 4,
            "meal_preparation_preference": "mixed",
            "refrigerator_access": True,
            "freezer_access": True,
            "cooking_equipment": ["stove"],
            "supplied_meals_per_week": 0,
            "supplied_meal_source": None,
            "foods_available_at_home": [],
            "favourite_foods": [],
            "disliked_foods": [],
            "never_suggest_foods": [],
            "refused_foods": [],
            "allergies": [],
            "intolerances": [],
            "dietary_pattern": "vegan",
            "religious_cultural_exclusions": [],
            "preferred_variety": "medium",
            "maximum_meal_repetition_per_week": 2,
            "accepts_leftovers": True,
            "accepts_batch_cooking": True,
            "work_shift_context": None,
            "daily_check_in_enabled": False,
            "preferred_check_in_time": None,
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["detail"]["code"] == "DIETARY_PATTERN_NOT_SUPPORTED_V1"


def test_legacy_vegetarian_profile_returns_unsupported_state_on_generation(
    client: TestClient, db: Session
) -> None:
    _setup_user_with_safety(client, "legacy-veg@example.com")
    response = client.put(
        "/api/v1/nutrition/profile",
        headers=ORIGIN,
        json={
            "daily_activity_level": "moderate",
            "individual_monthly_food_budget_irr": 100_000_000,
            "budget_style": "strict",
            "meals_per_day": 3,
            "snacks_per_day": 1,
            "preferred_plan_start_day": "saturday",
            "plan_style": "balanced",
            "cooking_skill": "basic",
            "maximum_cooking_time_minutes": 45,
            "cooking_frequency_per_week": 4,
            "meal_preparation_preference": "mixed",
            "refrigerator_access": True,
            "freezer_access": True,
            "cooking_equipment": ["stove"],
            "supplied_meals_per_week": 0,
            "supplied_meal_source": None,
            "foods_available_at_home": [],
            "favourite_foods": [],
            "disliked_foods": [],
            "never_suggest_foods": [],
            "refused_foods": [],
            "allergies": [],
            "intolerances": [],
            "dietary_pattern": "omnivore",
            "religious_cultural_exclusions": [],
            "preferred_variety": "medium",
            "maximum_meal_repetition_per_week": 2,
            "accepts_leftovers": True,
            "accepts_batch_cooking": True,
            "work_shift_context": None,
            "daily_check_in_enabled": False,
            "preferred_check_in_time": None,
        },
    )
    assert response.status_code == 200

    prof = db.query(NutritionProfile).first()
    assert prof is not None
    prof.dietary_pattern = DietaryPattern.VEGETARIAN
    db.commit()

    gen_resp = client.post("/api/v1/nutrition/plans", headers=ORIGIN)
    assert gen_resp.status_code == 201
    body = gen_resp.json()
    assert body["outcome"] == "failed"
    assert "DIETARY_PATTERN_NOT_SUPPORTED_V1" in body["reason_codes"]
