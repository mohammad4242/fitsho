from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.nutrition.enums import NutritionPlanLifecycleStatus, NutritionPlanReviewStatus
from app.nutrition.models import NutritionCatalogueFood, NutritionWeeklyPlan
from tests.nutrition.test_weekly_plan_api import (
    ORIGIN,
    _register_and_estimate,
    _seed_foods_and_prices,
)


def _setup(client: TestClient, db: Session) -> tuple[dict[str, object], NutritionCatalogueFood]:
    _register_and_estimate(client, "tracking-member@example.com")
    _seed_foods_and_prices(db)
    plan = client.post("/api/v1/nutrition/plans", headers=ORIGIN).json()["plan"]
    food = db.scalar(select(NutritionCatalogueFood).order_by(NutritionCatalogueFood.slug))
    assert food is not None
    return plan, food


def test_pending_plan_is_not_a_quick_check_in_baseline(
    client: TestClient, db: Session
) -> None:
    plan, food = _setup(client, db)
    entry_date = plan["start_date"]

    blocked = client.put(
        "/api/v1/nutrition/tracking/check-in",
        headers=ORIGIN,
        json={"entry_date": entry_date, "status": "on_plan"},
    )
    manual = client.post(
        "/api/v1/nutrition/tracking/entries/catalogue",
        headers=ORIGIN,
        json={"entry_date": entry_date, "food_id": str(food.id), "grams": 125},
    )

    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "ACTIVE_PLAN_REQUIRED"
    assert manual.status_code == 201
    assert manual.json()["source"] == "catalogue_manual"
    assert manual.json()["user_confirmed"] is True


def test_on_plan_confirmation_prefills_and_pins_exact_active_revision(
    client: TestClient, db: Session
) -> None:
    plan_json, _food = _setup(client, db)
    plan = db.scalar(select(NutritionWeeklyPlan).where(NutritionWeeklyPlan.id == plan_json["id"]))
    assert plan is not None and plan.review is not None
    plan.lifecycle_status = NutritionPlanLifecycleStatus.ACTIVE
    plan.review.status = NutritionPlanReviewStatus.APPROVED
    db.flush()

    response = client.put(
        "/api/v1/nutrition/tracking/check-in",
        headers=ORIGIN,
        json={"entry_date": plan.start_date.isoformat(), "status": "on_plan"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["check_in_status"] == "on_plan"
    assert body["plan_revision_id"] == str(plan.id)
    assert body["data_status"] == "sufficient"
    assert body["entries"]
    assert all(entry["source"] == "planned_confirmed" for entry in body["entries"])
    assert all(entry["plan_revision_id"] == str(plan.id) for entry in body["entries"])


def test_quick_approximation_is_explicitly_low_confidence_and_deletable(
    client: TestClient, db: Session
) -> None:
    _setup(client, db)
    created = client.post(
        "/api/v1/nutrition/tracking/entries/quick",
        headers=ORIGIN,
        json={
            "entry_date": date.today().isoformat(),
            "display_name": "یک وعده متوسط",
            "calories": 550,
            "protein_g": 25,
        },
    )
    assert created.status_code == 201
    assert created.json()["confidence"] == "low"
    assert created.json()["warning_codes"] == ["APPROXIMATE_INTAKE"]

    deleted = client.delete(
        f"/api/v1/nutrition/tracking/entries/{created.json()['id']}", headers=ORIGIN
    )
    summary = client.get(f"/api/v1/nutrition/tracking/days/{date.today().isoformat()}")
    assert deleted.status_code == 204
    assert summary.json()["data_status"] == "insufficient_data"
