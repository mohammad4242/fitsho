from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.nutrition.enums import NutritionPlanReviewStatus
from app.nutrition.models import NutritionPlanPhysicianReview, NutritionWeeklyPlan
from tests.nutrition.test_clinical_review_api import _login_physician
from tests.nutrition.test_weekly_plan_api import (
    ORIGIN,
    _register_and_estimate,
    _seed_foods_and_prices,
)


def _generated_plan(client: TestClient, db: Session) -> dict[str, object]:
    _register_and_estimate(client, "task7-member@example.com", meals=2, snacks=1)
    _seed_foods_and_prices(db)
    response = client.post("/api/v1/nutrition/plans", headers=ORIGIN)
    assert response.status_code == 201
    return response.json()["plan"]


def test_shopping_list_uses_exact_quantities_and_snapshot_costs(
    client: TestClient, db: Session
) -> None:
    plan = _generated_plan(client, db)

    response = client.get(f"/api/v1/nutrition/plans/{plan['id']}/shopping-list")

    assert response.status_code == 200
    body = response.json()
    assert body["plan_revision"] == plan["revision"]
    assert body["warning_codes"] == ["PLAN_NOT_ACTIVE"]
    assert body["total_cost_irr"] == plan["weekly_cost_irr"]
    assert all(item["required_quantity"] > 0 for item in body["items"])
    assert all(item["canonical_unit"] == "g" for item in body["items"])
    assert all("package_count" not in item for item in body["items"])


def test_metadata_changes_do_not_invalidate_review(client: TestClient, db: Session) -> None:
    plan = _generated_plan(client, db)
    meal_id = plan["days"][0]["meals"][0]["id"]

    lock = client.put(
        f"/api/v1/nutrition/plans/{plan['id']}/meals/{meal_id}/lock",
        headers=ORIGIN,
        json={"is_locked": True},
    )
    feedback = client.put(
        f"/api/v1/nutrition/plans/{plan['id']}/meals/{meal_id}/feedback",
        headers=ORIGIN,
        json={"feedback_type": "liked"},
    )

    assert lock.status_code == 200
    assert lock.json()["change_kind"] == "plan_control_metadata"
    assert feedback.status_code == 200
    persisted = db.scalar(select(NutritionWeeklyPlan).where(NutritionWeeklyPlan.id == plan["id"]))
    assert persisted is not None
    assert persisted.review is not None
    assert persisted.review.status == NutritionPlanReviewStatus.PENDING


def test_plan_defining_edit_creates_immutable_revision_and_rejects_stale_confirmation(
    client: TestClient, db: Session
) -> None:
    plan = _generated_plan(client, db)
    meal_id = plan["days"][0]["meals"][0]["id"]
    preview = client.post(
        f"/api/v1/nutrition/plans/{plan['id']}/edits/remove-meal/preview",
        params={"meal_id": meal_id},
    )
    assert preview.status_code == 200
    assert preview.json()["change_kind"] == "plan_defining"
    assert preview.json()["requires_physician_review"] is True

    confirmed = client.post(
        f"/api/v1/nutrition/plans/{plan['id']}/edits/remove-meal/confirm",
        headers=ORIGIN,
        json={"expected_plan_revision_id": plan["id"], "meal_id": meal_id},
    )
    assert confirmed.status_code == 200, confirmed.text
    revised = confirmed.json()
    assert revised["id"] != plan["id"]
    assert revised["revision"] == plan["revision"] + 1
    assert revised["review_status"] == "pending"
    assert revised["weekly_cost_irr"] < plan["weekly_cost_irr"]
    assert (
        revised["nutrients"]["goal_calories"]["planned"]
        < plan["nutrients"]["goal_calories"]["planned"]
    )

    old_review = db.scalar(
        select(NutritionPlanPhysicianReview).where(
            NutritionPlanPhysicianReview.plan_id == plan["id"]
        )
    )
    assert old_review is not None
    assert old_review.status == NutritionPlanReviewStatus.INVALIDATED_BY_REVISION

    stale = client.post(
        f"/api/v1/nutrition/plans/{plan['id']}/edits/remove-meal/confirm",
        headers=ORIGIN,
        json={"expected_plan_revision_id": revised["id"], "meal_id": meal_id},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "STALE_PLAN_REVISION"


def test_meal_replacement_preview_and_confirmation_create_revision(
    client: TestClient, db: Session
) -> None:
    plan = _generated_plan(client, db)
    target = plan["days"][0]["meals"][0]
    replacement = next(
        meal
        for meal in plan["days"][1]["meals"]
        if meal["slot_role"] == target["slot_role"] and meal["id"] != target["id"]
    )
    payload = {
        "expected_plan_revision_id": plan["id"],
        "meal_id": target["id"],
        "replacement_meal_id": replacement["id"],
    }
    preview = client.post(
        f"/api/v1/nutrition/plans/{plan['id']}/edits/replace-meal/preview", json=payload
    )
    assert preview.status_code == 200
    assert preview.json()["change_kind"] == "plan_defining"
    confirmed = client.post(
        f"/api/v1/nutrition/plans/{plan['id']}/edits/replace-meal/confirm",
        headers=ORIGIN,
        json=payload,
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["revision"] == plan["revision"] + 1
    assert confirmed.json()["physician_change_summary"][0]["operation"] == "replace_meal"


def test_food_replacement_and_partial_regeneration_preserve_immutable_history(
    client: TestClient, db: Session
) -> None:
    plan = _generated_plan(client, db)
    target_meal = plan["days"][0]["meals"][0]
    target_food = target_meal["foods"][0]
    replacement_food = next(
        food
        for day in plan["days"]
        for meal in day["meals"]
        for food in meal["foods"]
        if food["food_id"] != target_food["food_id"]
    )
    payload = {
        "expected_plan_revision_id": plan["id"],
        "meal_id": target_meal["id"],
        "food_id": target_food["food_id"],
        "replacement_food_id": replacement_food["food_id"],
    }
    assert (
        client.post(
            f"/api/v1/nutrition/plans/{plan['id']}/edits/replace-food/preview", json=payload
        ).status_code
        == 200
    )
    replaced = client.post(
        f"/api/v1/nutrition/plans/{plan['id']}/edits/replace-food/confirm",
        headers=ORIGIN,
        json=payload,
    )
    assert replaced.status_code == 200, replaced.text
    revision = replaced.json()
    regenerated = client.post(
        f"/api/v1/nutrition/plans/{revision['id']}/edits/partial-regenerate",
        headers=ORIGIN,
        json={"expected_plan_revision_id": revision["id"], "day_indexes": [0]},
    )
    assert regenerated.status_code == 200, regenerated.text
    assert regenerated.json()["revision"] == plan["revision"] + 2
    history = client.get("/api/v1/nutrition/plans/history").json()
    assert {item["id"] for item in history}.issuperset(
        {plan["id"], revision["id"], regenerated.json()["id"]}
    )


def test_physician_quantity_edit_rebinds_review_to_new_revision(
    client: TestClient,
    db: Session,
) -> None:
    plan = _generated_plan(client, db)
    physician = _login_physician(client, db, "quantity-physician@example.com")
    review = next(
        item
        for item in client.get("/api/v1/nutrition/physician/reviews").json()
        if item["plan_id"] == plan["id"]
    )
    assert client.post(
        f"/api/v1/nutrition/physician/reviews/{review['review_id']}/claim",
        headers=ORIGIN,
    ).status_code == 200
    meal = plan["days"][0]["meals"][0]
    food = meal["foods"][0]

    response = client.post(
        f"/api/v1/nutrition/physician/plans/{plan['id']}/edits/food-quantity",
        headers=ORIGIN,
        json={
            "expected_plan_revision_id": plan["id"],
            "meal_id": meal["id"],
            "food_id": food["food_id"],
            "grams": float(food["grams"]) + 10,
        },
    )

    assert response.status_code == 200, response.text
    revised = response.json()
    assert revised["id"] != plan["id"]
    assert revised["review_status"] == "in_review"
    new_review = db.scalar(
        select(NutritionPlanPhysicianReview).where(
            NutritionPlanPhysicianReview.plan_id == revised["id"]
        )
    )
    assert new_review is not None and new_review.physician_user_id == physician.id
