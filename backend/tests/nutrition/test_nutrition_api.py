from datetime import date
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.nutrition.models import (
    MedicalConditionPolicy,
    NutritionFoodItem,
    NutritionMedicalCondition,
    NutritionMedication,
    NutritionProfile,
    NutritionSafetyDecision,
)
from app.profile.models import BodyMeasurement, UserProfile

ORIGIN = {"Origin": "http://localhost:5173"}


def register(client: TestClient, email: str) -> UUID:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def select_nutrition_mode(client: TestClient) -> None:
    response = client.post(
        "/api/v1/profile/mode",
        headers=ORIGIN,
        json={"product_mode": "nutrition"},
    )
    assert response.status_code == 201


def adult_birth_date() -> str:
    today = date.today()
    return date(today.year - 25, today.month, min(today.day, 28)).isoformat()


def shared_payload(*, birth_date: str | None = None) -> dict[str, object]:
    return {
        "display_name": "  سارا  ",
        "birth_date": birth_date or adult_birth_date(),
        "sex": "female",
        "height_cm": 165,
        "current_weight_kg": 62.5,
        "fitness_goal": "maintain_weight",
    }


def standard_safety_payload() -> dict[str, object]:
    return {
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
    }


def nutrition_payload() -> dict[str, object]:
    return {
        "individual_monthly_food_budget_irr": 13_000_000,
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
        "cooking_equipment": ["stove", "refrigerator"],
        "supplied_meals_per_week": 2,
        "supplied_meal_source": "محل کار",
        "foods_available_at_home": ["برنج", "عدس"],
        "favourite_foods": ["مرغ"],
        "disliked_foods": ["کرفس"],
        "never_suggest_foods": ["دل و جگر"],
        "refused_foods": ["سیرابی"],
        "allergies": [{"name": "بادام زمینی", "details": "واکنش شدید"}],
        "intolerances": [{"name": "لاکتوز", "details": None}],
        "dietary_pattern": "omnivore",
        "religious_cultural_exclusions": ["الکل"],
        "preferred_variety": "medium",
        "maximum_meal_repetition_per_week": 2,
        "accepts_leftovers": True,
        "accepts_batch_cooking": True,
        "work_shift_context": "روزکار",
        "daily_check_in_enabled": True,
        "preferred_check_in_time": "21:30:00",
    }


def create_shared_and_safety(client: TestClient, email: str = "nutrition@example.com") -> UUID:
    user_id = register(client, email)
    select_nutrition_mode(client)
    shared = client.put("/api/v1/profile/shared", headers=ORIGIN, json=shared_payload())
    assert shared.status_code == 200
    safety = client.put(
        "/api/v1/nutrition/safety",
        headers=ORIGIN,
        json=standard_safety_payload(),
    )
    assert safety.status_code == 200
    return user_id


def test_under_18_shared_profile_is_rejected_with_stable_domain_error(
    client: TestClient,
    db: Session,
) -> None:
    user_id = register(client, "minor@example.com")
    select_nutrition_mode(client)
    today = date.today()
    minor_birth_date = date(today.year - 17, today.month, min(today.day, 28)).isoformat()

    response = client.put(
        "/api/v1/profile/shared",
        headers=ORIGIN,
        json=shared_payload(birth_date=minor_birth_date),
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": {
            "code": "AGE_NOT_SUPPORTED",
            "message": "فیتشو در حال حاضر فقط برای افراد ۱۸ سال و بالاتر ارائه می‌شود.",
        }
    }
    profile = db.get(UserProfile, user_id)
    assert profile is not None
    assert profile.birth_date is None
    assert db.scalar(select(BodyMeasurement).where(BodyMeasurement.user_id == user_id)) is None


def test_shared_profile_updates_the_single_source_of_truth(client: TestClient, db: Session) -> None:
    user_id = register(client, "shared@example.com")
    select_nutrition_mode(client)

    response = client.put(
        "/api/v1/profile/shared",
        headers=ORIGIN,
        json=shared_payload(),
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "سارا"
    assert response.json()["current_weight_kg"] == 62.5
    profile = db.get(UserProfile, user_id)
    assert profile is not None
    assert profile.display_name == "سارا"
    assert db.scalar(select(BodyMeasurement).where(BodyMeasurement.user_id == user_id)) is not None


@pytest.mark.parametrize(
    ("patch", "outcome", "can_continue"),
    [
        ({}, "standard_automatic", True),
        (
            {"conditions": [{"code": "controlled_hypertension", "details": "کنترل شده"}]},
            "automatic_draft_requires_physician_review",
            True,
        ),
        (
            {"conditions": [{"code": "kidney_disease", "details": None}]},
            "physician_manual_plan_required",
            False,
        ),
        (
            {"emergency_or_danger_symptoms": True},
            "unsupported_or_hard_blocked",
            False,
        ),
    ],
)
def test_early_safety_screen_returns_structured_versioned_outcomes(
    client: TestClient,
    patch: dict[str, object],
    outcome: str,
    can_continue: bool,
) -> None:
    register(client, f"{outcome}@example.com")
    select_nutrition_mode(client)
    assert (
        client.put("/api/v1/profile/shared", headers=ORIGIN, json=shared_payload()).status_code
        == 200
    )

    response = client.put(
        "/api/v1/nutrition/safety",
        headers=ORIGIN,
        json={**standard_safety_payload(), **patch},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["outcome"] == outcome
    assert result["policy_version"] == "medical-condition-v1"
    assert result["reason_codes"]
    assert result["can_continue_onboarding"] is can_continue
    assert result["requires_physician_review"] is (outcome != "standard_automatic")


def test_safety_screen_normalizes_conditions_and_medications(
    client: TestClient,
    db: Session,
) -> None:
    user_id = register(client, "medical@example.com")
    select_nutrition_mode(client)
    assert (
        client.put("/api/v1/profile/shared", headers=ORIGIN, json=shared_payload()).status_code
        == 200
    )
    payload = {
        **standard_safety_payload(),
        "conditions": [{"code": "lipid_disorder", "details": "  تحت کنترل  "}],
        "medications": [{"name": "  داروی نمونه  ", "dosage": "روزانه", "notes": None}],
    }

    response = client.put("/api/v1/nutrition/safety", headers=ORIGIN, json=payload)

    assert response.status_code == 200
    conditions = db.scalars(
        select(NutritionMedicalCondition).where(NutritionMedicalCondition.user_id == user_id)
    ).all()
    medications = db.scalars(
        select(NutritionMedication).where(NutritionMedication.user_id == user_id)
    ).all()
    assert [(item.code.value, item.details) for item in conditions] == [
        ("lipid_disorder", "تحت کنترل")
    ]
    assert [(item.name, item.dosage) for item in medications] == [("داروی نمونه", "روزانه")]


def test_safety_reassessment_keeps_append_only_decisions(client: TestClient, db: Session) -> None:
    user_id = register(client, "safety-history@example.com")
    select_nutrition_mode(client)
    assert (
        client.put("/api/v1/profile/shared", headers=ORIGIN, json=shared_payload()).status_code
        == 200
    )
    assert (
        client.put(
            "/api/v1/nutrition/safety", headers=ORIGIN, json=standard_safety_payload()
        ).status_code
        == 200
    )
    changed = client.put(
        "/api/v1/nutrition/safety",
        headers=ORIGIN,
        json={
            **standard_safety_payload(),
            "conditions": [{"code": "lipid_disorder", "details": None}],
        },
    )

    assert changed.status_code == 200
    assert changed.json()["outcome"] == "automatic_draft_requires_physician_review"
    decisions = db.scalars(
        select(NutritionSafetyDecision).where(NutritionSafetyDecision.user_id == user_id)
    ).all()
    assert len(decisions) == 2
    assert db.get(MedicalConditionPolicy, "medical-condition-v1") is not None


def test_nutrition_profile_persists_budget_and_normalized_food_constraints(
    client: TestClient,
    db: Session,
) -> None:
    user_id = create_shared_and_safety(client)

    response = client.put(
        "/api/v1/nutrition/profile",
        headers=ORIGIN,
        json=nutrition_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["currency"] == "IRR"
    assert body["individual_monthly_food_budget_irr"] == 13_000_000
    assert body["weekly_budget_irr"] == 3_000_000
    assert body["allergies"] == [{"name": "بادام زمینی", "details": "واکنش شدید"}]
    assert db.get(NutritionProfile, user_id) is not None
    items = db.scalars(select(NutritionFoodItem).where(NutritionFoodItem.user_id == user_id)).all()
    assert {item.kind.value for item in items} >= {"allergy", "intolerance", "favourite"}

    saved = client.get("/api/v1/nutrition/profile")
    assert saved.status_code == 200
    assert saved.json() == body
    status_response = client.get("/api/v1/profile/status")
    assert status_response.json()["completion_state"] == "nutrition_draft_ready"


def test_nutrition_profile_requires_completed_standard_or_reviewable_safety(
    client: TestClient,
) -> None:
    register(client, "unsafe-order@example.com")
    select_nutrition_mode(client)
    assert (
        client.put("/api/v1/profile/shared", headers=ORIGIN, json=shared_payload()).status_code
        == 200
    )

    missing = client.put("/api/v1/nutrition/profile", headers=ORIGIN, json=nutrition_payload())

    assert missing.status_code == 409
    assert missing.json()["detail"]["code"] == "SAFETY_SCREEN_REQUIRED"


def test_current_safety_and_review_requirement_are_available_without_recalculation(
    client: TestClient,
    db: Session,
) -> None:
    user_id = register(client, "review-status@example.com")
    select_nutrition_mode(client)
    assert (
        client.put("/api/v1/profile/shared", headers=ORIGIN, json=shared_payload()).status_code
        == 200
    )
    assert (
        client.put(
            "/api/v1/nutrition/safety",
            headers=ORIGIN,
            json={
                **standard_safety_payload(),
                "conditions": [{"code": "controlled_hypertension", "details": None}],
            },
        ).status_code
        == 200
    )

    safety = client.get("/api/v1/nutrition/safety")
    review = client.get("/api/v1/nutrition/review-requirement")

    assert safety.status_code == 200
    assert safety.json()["outcome"] == "automatic_draft_requires_physician_review"
    assert review.status_code == 200
    assert review.json() == {
        "required": True,
        "mode": "automatic_draft_review",
        "status": "not_requested",
        "safety_decision_id": safety.json()["id"],
    }
    assert (
        db.scalar(select(NutritionSafetyDecision).where(NutritionSafetyDecision.user_id == user_id))
        is not None
    )
    assert client.get("/api/v1/profile/status").json()["completion_state"] == (
        "medical_review_information_incomplete"
    )
    assert (
        client.put(
            "/api/v1/nutrition/profile", headers=ORIGIN, json=nutrition_payload()
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/profile/status").json()["completion_state"]
        == "nutrition_pending_review"
    )


def test_nutrition_mutations_require_authentication_and_trusted_origin(
    client: TestClient,
) -> None:
    assert client.get("/api/v1/nutrition/profile").status_code == 401
    register(client, "origin@example.com")
    select_nutrition_mode(client)
    assert client.put("/api/v1/profile/shared", json=shared_payload()).status_code == 403
    assert client.put("/api/v1/nutrition/safety", json=standard_safety_payload()).status_code == 403


def test_nutrition_profile_draft_cannot_use_training_capabilities(client: TestClient) -> None:
    register(client, "nutrition-capability@example.com")
    select_nutrition_mode(client)

    exercises = client.get("/api/v1/exercises")
    workout = client.get("/api/v1/workout-plans/active")

    assert exercises.status_code == 403
    assert workout.status_code == 403
