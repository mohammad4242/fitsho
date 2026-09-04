from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.nutrition.candidate_selection import quality_for_result
from app.nutrition.enums import NutritionPlanReviewStatus
from app.nutrition.models import (
    NutritionMealFeedback,
    NutritionPlanPhysicianReview,
    NutritionWeeklyPlan,
)
from app.nutrition.planner_engine import (
    GenerationOutcome,
    PlannedDay,
    PlannedMeal,
    PlannerResult,
)
from app.nutrition.preference_snapshot import load_preference_snapshot
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


def test_feedback_read_is_persisted_and_changes_future_candidate_scoring(
    client: TestClient, db: Session
) -> None:
    plan = _generated_plan(client, db)
    meal = plan["days"][0]["meals"][0]

    saved = client.put(
        f"/api/v1/nutrition/plans/{plan['id']}/meals/{meal['id']}/feedback",
        headers=ORIGIN,
        json={"feedback_type": "liked"},
    )
    assert saved.status_code == 200
    assert saved.json()["feedback_type"] == "liked"

    persisted_plan = db.scalar(
        select(NutritionWeeklyPlan).where(NutritionWeeklyPlan.id == plan["id"])
    )
    assert persisted_plan is not None
    row = db.scalar(
        select(NutritionMealFeedback).where(NutritionMealFeedback.meal_id == meal["id"])
    )
    assert row is not None
    snapshot = load_preference_snapshot(db, persisted_plan.user_id, ())
    assert snapshot.liked_meal_ids == (meal["catalogue_meal_id"],)

    result = PlannerResult(
        outcome=GenerationOutcome.SUCCESS,
        reason_codes=("SAFE_FEASIBLE_DRAFT_GENERATED",),
        days=(
            PlannedDay(
                day_index=0,
                meals=(
                    PlannedMeal(
                        role="main",
                        slot_index=0,
                        template_id=meal["catalogue_meal_id"],
                        template_category="main",
                        foods=(),
                        cost_irr=1,
                        nutrients=(),
                    ),
                ),
                cost_irr=1,
                nutrients=(),
            ),
        ),
        weekly_cost_irr=1,
    )
    neutral = quality_for_result(result, weekly_budget_irr=1)
    liked = quality_for_result(result, weekly_budget_irr=1, preference_snapshot=snapshot)
    assert liked.preference_and_feedback_penalty < neutral.preference_and_feedback_penalty

    read = client.get(f"/api/v1/nutrition/plans/{plan['id']}/feedback")
    assert read.status_code == 200
    assert read.json()["feedback"][meal["id"]] == "liked"

    switched = client.put(
        f"/api/v1/nutrition/plans/{plan['id']}/meals/{meal['id']}/feedback",
        headers=ORIGIN,
        json={"feedback_type": "disliked"},
    )
    assert switched.status_code == 200
    assert switched.json()["feedback_type"] == "disliked"
    updated_row = db.scalar(
        select(NutritionMealFeedback).where(NutritionMealFeedback.meal_id == meal["id"])
    )
    assert updated_row is not None and updated_row.feedback_type.value == "disliked"


def test_replacement_options_are_explicit_and_exclude_locked_meals(
    client: TestClient, db: Session
) -> None:
    plan = _generated_plan(client, db)
    target = plan["days"][0]["meals"][0]
    response = client.get(
        f"/api/v1/nutrition/plans/{plan['id']}/meal-replacement-options",
        params={"meal_id": target["id"]},
    )
    assert response.status_code == 200
    options = response.json()["options"]
    assert options
    assert all(option["id"] != target["id"] for option in options)
    assert all(option["slot_role"] == target["slot_role"] for option in options)
    assert all(not option["is_locked"] for option in options)

    food = target["foods"][0]
    food_options = client.get(
        f"/api/v1/nutrition/plans/{plan['id']}/food-replacement-options",
        params={"meal_id": target["id"], "food_id": food["food_id"]},
    )
    assert food_options.status_code == 200
    assert all(option["food_id"] != food["food_id"] for option in food_options.json()["options"])


def test_plan_defining_edits_reject_locked_meals_and_in_review_plans(
    client: TestClient, db: Session
) -> None:
    plan = _generated_plan(client, db)
    meal = plan["days"][0]["meals"][0]
    locked = client.put(
        f"/api/v1/nutrition/plans/{plan['id']}/meals/{meal['id']}/lock",
        headers=ORIGIN,
        json={"is_locked": True},
    )
    assert locked.status_code == 200
    locked_preview = client.post(
        f"/api/v1/nutrition/plans/{plan['id']}/edits/remove-meal/preview",
        params={"meal_id": meal["id"]},
    )
    assert locked_preview.status_code == 409
    assert locked_preview.json()["detail"]["code"] == "MEAL_LOCKED"

    persisted = db.scalar(select(NutritionWeeklyPlan).where(NutritionWeeklyPlan.id == plan["id"]))
    assert persisted is not None and persisted.review is not None
    persisted.review.status = NutritionPlanReviewStatus.IN_REVIEW
    db.commit()
    blocked = client.post(
        f"/api/v1/nutrition/plans/{plan['id']}/edits/remove-meal/confirm",
        headers=ORIGIN,
        json={"expected_plan_revision_id": plan["id"], "meal_id": meal["id"]},
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "PLAN_REVIEW_IN_PROGRESS"


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
    assert (
        client.post(
            f"/api/v1/nutrition/physician/reviews/{review['review_id']}/claim",
            headers=ORIGIN,
        ).status_code
        == 200
    )
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
