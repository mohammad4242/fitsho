from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.nutrition.clinical_service import ClinicalError, require_physician
from app.nutrition.enums import (
    NutritionMealFeedbackType,
    NutritionPlanGenerationOutcome,
    NutritionPlanLifecycleStatus,
    NutritionPlanReviewStatus,
)
from app.nutrition.models import (
    NutritionMealFeedback,
    NutritionPlanGeneration,
    NutritionPlanPhysicianReview,
    NutritionReviewAuditEvent,
    NutritionWeeklyPlan,
    NutritionWeeklyPlanDay,
    NutritionWeeklyPlanFood,
    NutritionWeeklyPlanMeal,
    NutritionWeeklyPlanNutrient,
)
from app.nutrition.plan_service import weekly_plan_response
from app.nutrition.schemas import WeeklyPlanResponse


class PlanEditError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code


def _query() -> Select[tuple[NutritionWeeklyPlan]]:
    return select(NutritionWeeklyPlan).options(
        selectinload(NutritionWeeklyPlan.review),
        selectinload(NutritionWeeklyPlan.nutrients),
        selectinload(NutritionWeeklyPlan.days)
        .selectinload(NutritionWeeklyPlanDay.meals)
        .selectinload(NutritionWeeklyPlanMeal.foods),
    )


def owned_plan(
    db: Session, user_id: UUID, plan_id: UUID, *, lock: bool = False
) -> NutritionWeeklyPlan:
    query = _query().where(
        NutritionWeeklyPlan.id == plan_id, NutritionWeeklyPlan.user_id == user_id
    )
    if lock:
        query = query.with_for_update()
    plan = db.scalar(query)
    if plan is None:
        raise PlanEditError("NUTRITION_PLAN_NOT_FOUND")
    return plan


def shopping_list(db: Session, user_id: UUID, plan_id: UUID) -> dict[str, object]:
    plan = owned_plan(db, user_id, plan_id)
    items: dict[UUID, dict[str, Any]] = {}
    for day in plan.days:
        for meal in day.meals:
            for food in meal.foods:
                item = items.setdefault(
                    food.food_id,
                    {
                        "food_id": food.food_id,
                        "slug": food.food_slug,
                        "name_fa": food.food_name_fa,
                        "name_en": food.food_name_en,
                        "required_quantity": Decimal(),
                        "canonical_unit": "g",
                        "cost_irr": 0,
                        "nutrients": defaultdict(Decimal),
                        "price_snapshot": food.price_snapshot,
                    },
                )
                item["required_quantity"] += food.grams
                item["cost_irr"] += food.cost_irr
                nutrients = item["nutrients"]
                for code, value in food.nutrient_snapshot.items():
                    nutrients[code] += Decimal(str(value))
    serialized = []
    for item in sorted(items.values(), key=lambda row: str(row["slug"])):
        item["required_quantity"] = float(item["required_quantity"])
        item["nutrients"] = {key: float(value) for key, value in item["nutrients"].items()}
        serialized.append(item)
    return {
        "plan_id": plan.id,
        "plan_revision": plan.revision,
        "approval_status": plan.review.status.value if plan.review else "missing",
        "warning_codes": []
        if plan.lifecycle_status == NutritionPlanLifecycleStatus.ACTIVE
        else ["PLAN_NOT_ACTIVE"],
        "items": serialized,
        "total_cost_irr": sum(int(item["cost_irr"]) for item in serialized),
    }


def set_meal_lock(
    db: Session, user_id: UUID, plan_id: UUID, meal_id: UUID, locked: bool
) -> dict[str, object]:
    plan = owned_plan(db, user_id, plan_id, lock=True)
    meal = next((meal for day in plan.days for meal in day.meals if meal.id == meal_id), None)
    if meal is None:
        raise PlanEditError("MEAL_NOT_FOUND")
    meal.is_locked = locked
    db.commit()
    return {
        "plan_id": plan.id,
        "plan_revision": plan.revision,
        "meal_id": meal.id,
        "is_locked": locked,
        "change_kind": "plan_control_metadata",
    }


def save_feedback(
    db: Session,
    user_id: UUID,
    plan_id: UUID,
    meal_id: UUID,
    kind: NutritionMealFeedbackType,
    notes: str | None,
) -> dict[str, object]:
    plan = owned_plan(db, user_id, plan_id)
    if not any(meal.id == meal_id for day in plan.days for meal in day.meals):
        raise PlanEditError("MEAL_NOT_FOUND")
    row = db.scalar(
        select(NutritionMealFeedback).where(
            NutritionMealFeedback.user_id == user_id, NutritionMealFeedback.meal_id == meal_id
        )
    )
    if row is None:
        row = NutritionMealFeedback(
            user_id=user_id, meal_id=meal_id, feedback_type=kind, notes=notes
        )
        db.add(row)
    else:
        row.feedback_type = kind
        row.notes = notes
    db.commit()
    return {"meal_id": meal_id, "feedback_type": kind.value, "change_kind": "plan_control_metadata"}


def preview_remove_meal(
    db: Session, user_id: UUID, plan_id: UUID, meal_id: UUID
) -> dict[str, object]:
    plan = owned_plan(db, user_id, plan_id)
    meal = next((meal for day in plan.days for meal in day.meals if meal.id == meal_id), None)
    if meal is None:
        raise PlanEditError("MEAL_NOT_FOUND")
    return {
        "plan_id": plan.id,
        "expected_plan_revision_id": plan.id,
        "expected_revision": plan.revision,
        "operation": "remove_meal",
        "meal_id": meal.id,
        "daily_delta": {key: -float(str(value)) for key, value in meal.nutrient_totals.items()},
        "weekly_cost_delta_irr": -meal.cost_irr,
        "new_warning_codes": ["MEAL_REMOVAL_MAY_REDUCE_ADEQUACY"],
        "requires_physician_review": True,
        "change_kind": "plan_defining",
    }


def _copy_food(food: NutritionWeeklyPlanFood) -> NutritionWeeklyPlanFood:
    return NutritionWeeklyPlanFood(
        food_id=food.food_id,
        food_slug=food.food_slug,
        food_name_fa=food.food_name_fa,
        food_name_en=food.food_name_en,
        grams=food.grams,
        cost_irr=food.cost_irr,
        nutrient_snapshot=dict(food.nutrient_snapshot),
        price_snapshot=dict(food.price_snapshot),
    )


def _sum_maps(maps: list[dict[str, object]]) -> dict[str, str]:
    totals: defaultdict[str, Decimal] = defaultdict(Decimal)
    for values in maps:
        for key, value in values.items():
            totals[key] += Decimal(str(value))
    return {key: str(value) for key, value in totals.items()}


def confirm_remove_meal(
    db: Session,
    user_id: UUID,
    plan_id: UUID,
    expected_plan_revision_id: UUID,
    meal_id: UUID,
    *,
    physician_id: UUID | None = None,
) -> WeeklyPlanResponse:
    plan = owned_plan(db, user_id, plan_id, lock=True)
    if plan.id != expected_plan_revision_id:
        raise PlanEditError("STALE_PLAN_REVISION")
    if (
        physician_id is None
        and plan.review
        and plan.review.status == NutritionPlanReviewStatus.IN_REVIEW
    ):
        raise PlanEditError("PLAN_REVIEW_IN_PROGRESS")
    if not any(meal.id == meal_id for day in plan.days for meal in day.meals):
        raise PlanEditError("MEAL_NOT_FOUND")
    latest = (
        db.scalar(
            select(func.max(NutritionWeeklyPlan.revision)).where(
                NutritionWeeklyPlan.user_id == user_id
            )
        )
        or 0
    )
    generation = db.get(NutritionPlanGeneration, plan.generation_id)
    if generation is None:
        raise PlanEditError("PLAN_GENERATION_NOT_FOUND")
    copied_generation = NutritionPlanGeneration(
        user_id=user_id,
        estimate_id=generation.estimate_id,
        safety_decision_id=generation.safety_decision_id,
        outcome=NutritionPlanGenerationOutcome.SUCCESS,
        reason_codes=[],
        warning_codes=["USER_PLAN_EDIT"],
        input_signature=generation.input_signature,
        input_snapshot=dict(generation.input_snapshot),
        diagnostic_snapshot={"source_plan_id": str(plan.id), "operation": "remove_meal"},
        planner_policy_version=generation.planner_policy_version,
        planner_version=generation.planner_version,
    )
    db.add(copied_generation)
    db.flush()
    days: list[NutritionWeeklyPlanDay] = []
    for day in plan.days:
        meals = [
            NutritionWeeklyPlanMeal(
                slot_role=meal.slot_role,
                slot_index=meal.slot_index,
                target_distribution=dict(meal.target_distribution),
                nutrient_totals=dict(meal.nutrient_totals),
                cost_irr=meal.cost_irr,
                is_locked=meal.is_locked,
                foods=[_copy_food(food) for food in meal.foods],
            )
            for meal in day.meals
            if meal.id != meal_id
        ]
        days.append(
            NutritionWeeklyPlanDay(
                day_index=day.day_index,
                plan_date=day.plan_date,
                cost_irr=sum(meal.cost_irr for meal in meals),
                nutrient_totals=_sum_maps([meal.nutrient_totals for meal in meals]),
                meals=meals,
            )
        )
    revision = latest + 1
    new_plan = NutritionWeeklyPlan(
        user_id=user_id,
        generation_id=copied_generation.id,
        estimate_id=plan.estimate_id,
        safety_decision_id=plan.safety_decision_id,
        revision=revision,
        supersedes_plan_id=plan.id,
        lineage_id=plan.lineage_id,
        lifecycle_status=NutritionPlanLifecycleStatus.PENDING_PHYSICIAN_REVIEW,
        is_user_visible=True,
        start_date=plan.start_date,
        planner_policy_version=plan.planner_policy_version,
        planner_version=plan.planner_version,
        scientific_policy_version=plan.scientific_policy_version,
        formula_version=plan.formula_version,
        food_data_manifest=dict(plan.food_data_manifest),
        input_snapshot=dict(plan.input_snapshot),
        price_snapshot=dict(plan.price_snapshot),
        repair_snapshot=list(plan.repair_snapshot),
        warning_codes=list(set(plan.warning_codes + ["USER_PLAN_EDIT"])),
        explanation_codes=list(plan.explanation_codes),
        weekly_cost_irr=sum(day.cost_irr for day in days),
        weekly_budget_irr=plan.weekly_budget_irr,
        budget_status=plan.budget_status,
        days=days,
        nutrients=[
            NutritionWeeklyPlanNutrient(
                nutrient_code=row.nutrient_code,
                unit=row.unit,
                reference_kind=row.reference_kind,
                preferred_value=row.preferred_value,
                minimum_or_maximum_value=row.minimum_or_maximum_value,
                planned_value=row.planned_value,
                difference_from_preferred=row.difference_from_preferred,
                difference_from_limit=row.difference_from_limit,
                status=row.status,
                reason_codes=list(row.reason_codes),
                data_confidence=row.data_confidence,
                explanation_codes=list(row.explanation_codes),
            )
            for row in plan.nutrients
        ],
        review=NutritionPlanPhysicianReview(
            status=(
                NutritionPlanReviewStatus.IN_REVIEW
                if physician_id
                else NutritionPlanReviewStatus.PENDING
            ),
            expected_plan_revision=revision,
            physician_user_id=physician_id,
            assigned_at=datetime.now(UTC) if physician_id else None,
            review_started_at=datetime.now(UTC) if physician_id else None,
            structured_change_summary=[
                {"operation": "remove_meal", "source_plan_id": str(plan.id)}
            ],
        ),
    )
    if plan.review and plan.review.status in {
        NutritionPlanReviewStatus.PENDING,
        NutritionPlanReviewStatus.IN_REVIEW,
        NutritionPlanReviewStatus.CHANGES_REQUESTED,
    }:
        plan.review.status = NutritionPlanReviewStatus.INVALIDATED_BY_REVISION
        plan.review.invalidated_at = datetime.now(UTC)
        plan.review.invalidation_reason = "PLAN_DEFINING_REVISION"
        plan.lifecycle_status = NutritionPlanLifecycleStatus.ARCHIVED
    db.add(new_plan)
    db.commit()
    db.refresh(new_plan)
    return weekly_plan_response(owned_plan(db, user_id, new_plan.id))


def physician_remove_meal(
    db: Session,
    physician_id: UUID,
    plan_id: UUID,
    expected_plan_revision_id: UUID,
    meal_id: UUID,
) -> WeeklyPlanResponse:
    try:
        require_physician(db, physician_id)
    except ClinicalError as error:
        raise PlanEditError("PHYSICIAN_ROLE_REQUIRED") from error
    plan = db.scalar(select(NutritionWeeklyPlan).where(NutritionWeeklyPlan.id == plan_id))
    if plan is None:
        raise PlanEditError("NUTRITION_PLAN_NOT_FOUND")
    return confirm_remove_meal(
        db,
        plan.user_id,
        plan_id,
        expected_plan_revision_id,
        meal_id,
        physician_id=physician_id,
    )


def physician_action(
    db: Session,
    physician_id: UUID,
    plan_id: UUID,
    expected_plan_revision_id: UUID,
    action: str,
    notes: str | None,
) -> WeeklyPlanResponse:
    try:
        require_physician(db, physician_id)
    except ClinicalError as error:
        raise PlanEditError("PHYSICIAN_ROLE_REQUIRED") from error
    plan = db.scalar(_query().where(NutritionWeeklyPlan.id == plan_id).with_for_update())
    if plan is None:
        raise PlanEditError("NUTRITION_PLAN_NOT_FOUND")
    if (
        plan.id != expected_plan_revision_id
        or not plan.review
        or plan.review.expected_plan_revision != plan.revision
    ):
        raise PlanEditError("STALE_PLAN_REVISION")
    now = datetime.now(UTC)
    plan.review.physician_user_id = physician_id
    plan.review.user_visible_notes = notes
    if action == "start_review":
        plan.review.status = NutritionPlanReviewStatus.IN_REVIEW
        plan.lifecycle_status = NutritionPlanLifecycleStatus.PHYSICIAN_REVIEW_IN_PROGRESS
        plan.review.review_started_at = now
    elif action == "approve":
        plan.review.status = NutritionPlanReviewStatus.APPROVED
        plan.review.reviewed_at = now
        if plan.start_date <= now.date():
            plan.lifecycle_status = NutritionPlanLifecycleStatus.ACTIVE
            for old in db.scalars(
                select(NutritionWeeklyPlan).where(
                    NutritionWeeklyPlan.user_id == plan.user_id,
                    NutritionWeeklyPlan.id != plan.id,
                    NutritionWeeklyPlan.lifecycle_status == NutritionPlanLifecycleStatus.ACTIVE,
                )
            ):
                old.lifecycle_status = NutritionPlanLifecycleStatus.ARCHIVED
        else:
            plan.lifecycle_status = NutritionPlanLifecycleStatus.PHYSICIAN_APPROVED
    elif action == "request_changes":
        plan.review.status = NutritionPlanReviewStatus.CHANGES_REQUESTED
        plan.lifecycle_status = NutritionPlanLifecycleStatus.CHANGES_REQUESTED
    elif action == "reject":
        plan.review.status = NutritionPlanReviewStatus.REJECTED
        plan.review.reviewed_at = now
        plan.lifecycle_status = NutritionPlanLifecycleStatus.REJECTED
    else:
        raise PlanEditError("INVALID_REVIEW_ACTION")
    db.add(
        NutritionReviewAuditEvent(
            review_id=plan.review.id,
            actor_user_id=physician_id,
            action=action,
            metadata_snapshot={"plan_id": str(plan.id), "revision": plan.revision},
        )
    )
    db.commit()
    return weekly_plan_response(owned_plan(db, plan.user_id, plan.id))
