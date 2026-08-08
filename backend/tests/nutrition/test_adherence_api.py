from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.nutrition.enums import NutritionPlanLifecycleStatus, NutritionPlanReviewStatus
from app.nutrition.models import NutritionTargetUpdateConsent, NutritionWeeklyPlan
from tests.nutrition.test_weekly_plan_api import (
    ORIGIN,
    _register_and_estimate,
    _seed_foods_and_prices,
)


def _active_plan(client: TestClient, db: Session) -> NutritionWeeklyPlan:
    _register_and_estimate(client, "adherence-member@example.com")
    _seed_foods_and_prices(db)
    plan_id = client.post("/api/v1/nutrition/plans", headers=ORIGIN).json()["plan"]["id"]
    plan = db.scalar(select(NutritionWeeklyPlan).where(NutritionWeeklyPlan.id == plan_id))
    assert plan is not None and plan.review is not None
    plan.lifecycle_status = NutritionPlanLifecycleStatus.ACTIVE
    plan.review.status = NutritionPlanReviewStatus.APPROVED
    db.flush()
    return plan


def test_adherence_is_component_based_confidence_aware_and_keeps_insufficient_data(
    client: TestClient, db: Session
) -> None:
    plan = _active_plan(client, db)
    assert (
        client.put(
            "/api/v1/nutrition/tracking/check-in",
            headers=ORIGIN,
            json={"entry_date": plan.start_date.isoformat(), "status": "on_plan"},
        ).status_code
        == 200
    )

    end = plan.start_date + timedelta(days=1)
    response = client.get(
        "/api/v1/nutrition/adherence",
        params={"start": plan.start_date.isoformat(), "end": end.isoformat()},
    )

    assert response.status_code == 200
    body = response.json()
    first, second = body["days"]
    assert first["status"] == "sufficient"
    assert first["calorie_adherence"] is not None
    assert first["protein_adherence"] is not None
    assert first["meal_adherence"] == 100
    assert first["formula_version"] == "nutrition-adherence-v1"
    assert second["status"] == "insufficient_data"
    assert second["composite_score"] is None
    assert body["weight_causality_claimed"] is False


def test_scientific_target_change_requires_explicit_confirmation(
    client: TestClient, db: Session
) -> None:
    _active_plan(client, db)
    blocked = client.post(
        "/api/v1/nutrition/targets/confirm-update",
        headers=ORIGIN,
        json={"requested_goal": "lose_weight", "confirmed": False},
    )
    assert blocked.status_code == 409
    assert db.scalar(select(NutritionTargetUpdateConsent)) is None

    changed = client.post(
        "/api/v1/nutrition/targets/confirm-update",
        headers=ORIGIN,
        json={"requested_goal": "lose_weight", "confirmed": True},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["user_confirmed"] is True
    audit = db.scalar(select(NutritionTargetUpdateConsent))
    assert audit is not None and audit.estimate_id is not None
