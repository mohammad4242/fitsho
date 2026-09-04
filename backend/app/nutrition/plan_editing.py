from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, selectinload

from app.nutrition.clinical_service import ClinicalError, require_physician
from app.nutrition.enums import (
    NutritionMealFeedbackType,
    NutritionPlanBudgetStatus,
    NutritionPlanGenerationOutcome,
    NutritionPlanLifecycleStatus,
    NutritionPlanReviewStatus,
    NutritionPlanRole,
)
from app.nutrition.models import (
    NutritionCatalogueFood,
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
        selectinload(NutritionWeeklyPlan.generation),
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
                if food.item_kind == "prepared_recipe" and food.recipe_snapshot is not None:
                    raw_ingredients = food.recipe_snapshot.get("ingredients", [])
                    if isinstance(raw_ingredients, list):
                        for ingredient in raw_ingredients:
                            if isinstance(ingredient, dict):
                                _add_shopping_snapshot_item(items, ingredient)
                    continue
                if food.food_id is None:
                    continue
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


def _add_shopping_snapshot_item(
    items: dict[UUID, dict[str, Any]], ingredient: dict[str, object]
) -> None:
    try:
        food_id = UUID(str(ingredient["food_id"]))
        grams = Decimal(str(ingredient["grams"]))
        cost = int(Decimal(str(ingredient["cost_irr"])))
    except (KeyError, TypeError, ValueError):
        return
    item = items.setdefault(
        food_id,
        {
            "food_id": food_id,
            "slug": str(ingredient.get("slug", "")),
            "name_fa": str(ingredient.get("name_fa", "")),
            "name_en": str(ingredient.get("name_en", "")),
            "required_quantity": Decimal(),
            "canonical_unit": "g",
            "cost_irr": 0,
            "nutrients": defaultdict(Decimal),
            "price_snapshot": {"reference_id": ingredient.get("price_reference_id")},
        },
    )
    item["required_quantity"] += grams
    item["cost_irr"] += cost
    nutrients = ingredient.get("nutrients", {})
    if isinstance(nutrients, dict):
        for code, value in nutrients.items():
            item["nutrients"][str(code)] += Decimal(str(value))


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


def meal_feedback(db: Session, user_id: UUID, plan_id: UUID) -> dict[str, object]:
    plan = owned_plan(db, user_id, plan_id)
    meal_ids = [meal.id for day in plan.days for meal in day.meals]
    rows = db.scalars(
        select(NutritionMealFeedback).where(
            NutritionMealFeedback.user_id == user_id,
            NutritionMealFeedback.meal_id.in_(meal_ids),
        )
    ).all()
    return {"feedback": {str(row.meal_id): row.feedback_type.value for row in rows}}


def meal_replacement_options(
    db: Session, user_id: UUID, plan_id: UUID, meal_id: UUID
) -> dict[str, object]:
    plan = owned_plan(db, user_id, plan_id)
    target = next((meal for day in plan.days for meal in day.meals if meal.id == meal_id), None)
    if target is None:
        raise PlanEditError("MEAL_NOT_FOUND")
    if target.is_locked:
        raise PlanEditError("MEAL_LOCKED")
    options = [
        meal
        for day in plan.days
        for meal in day.meals
        if meal.id != target.id and meal.slot_role == target.slot_role and not meal.is_locked
    ]
    return {
        "target_meal_id": target.id,
        "options": [
            {
                "id": meal.id,
                "name_fa": meal.catalogue_meal.name_fa if meal.catalogue_meal else "وعده غذایی",
                "name_en": meal.catalogue_meal.name_en if meal.catalogue_meal else "Meal",
                "meal_code": meal.catalogue_meal.code if meal.catalogue_meal else "",
                "image_url": meal.catalogue_meal.image_path if meal.catalogue_meal else None,
                "slot_role": meal.slot_role.value,
                "nutrient_totals": _float_map(meal.nutrient_totals),
                "cost_irr": meal.cost_irr,
                "is_locked": meal.is_locked,
            }
            for meal in options
        ],
    }


def food_replacement_options(
    db: Session, user_id: UUID, plan_id: UUID, meal_id: UUID, food_id: UUID
) -> dict[str, object]:
    plan = owned_plan(db, user_id, plan_id)
    target_meal = next(
        (meal for day in plan.days for meal in day.meals if meal.id == meal_id), None
    )
    if target_meal is None:
        raise PlanEditError("MEAL_NOT_FOUND")
    if target_meal.is_locked:
        raise PlanEditError("MEAL_LOCKED")
    target = next((food for food in target_meal.foods if food.food_id == food_id), None)
    if target is None:
        raise PlanEditError("FOOD_REPLACEMENT_NOT_FOUND")
    assert target.food_id is not None
    source_by_food_id: dict[UUID, NutritionWeeklyPlanFood] = {}
    for day in plan.days:
        for meal in day.meals:
            if meal.is_locked:
                continue
            for food in meal.foods:
                if food.food_id is not None and food.food_id != target.food_id:
                    source_by_food_id.setdefault(food.food_id, food)
    catalogue_foods = {
        food.id: food
        for food in db.scalars(
            select(NutritionCatalogueFood).where(NutritionCatalogueFood.id.in_(source_by_food_id))
        )
    }
    options = []
    for source_food_id, source in sorted(source_by_food_id.items(), key=lambda item: str(item[0])):
        scaled = _scaled_food(source, target.grams)
        catalogue_food = catalogue_foods.get(source_food_id)
        options.append(
            {
                "food_id": source_food_id,
                "slug": source.food_slug,
                "name_fa": source.food_name_fa,
                "name_en": source.food_name_en,
                "image_url": catalogue_food.image_path if catalogue_food else None,
                "grams": float(scaled.grams),
                "cost_irr": scaled.cost_irr,
                "nutrients": _float_map(scaled.nutrient_snapshot),
            }
        )
    return {"target_meal_id": target_meal.id, "target_food_id": target.food_id, "options": options}


def preview_remove_meal(
    db: Session, user_id: UUID, plan_id: UUID, meal_id: UUID
) -> dict[str, object]:
    plan = owned_plan(db, user_id, plan_id)
    meal = next((meal for day in plan.days for meal in day.meals if meal.id == meal_id), None)
    if meal is None:
        raise PlanEditError("MEAL_NOT_FOUND")
    if meal.is_locked:
        raise PlanEditError("MEAL_LOCKED")
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


def _copy_meal(
    meal: NutritionWeeklyPlanMeal, *, slot_index: int | None = None
) -> NutritionWeeklyPlanMeal:
    return NutritionWeeklyPlanMeal(
        catalogue_meal_id=meal.catalogue_meal_id,
        catalogue_meal_category=meal.catalogue_meal_category,
        slot_role=meal.slot_role,
        slot_index=meal.slot_index if slot_index is None else slot_index,
        target_distribution=dict(meal.target_distribution),
        nutrient_totals=dict(meal.nutrient_totals),
        cost_irr=meal.cost_irr,
        is_locked=meal.is_locked,
        foods=[_copy_food(food) for food in meal.foods],
    )


def _create_revision(
    db: Session,
    plan: NutritionWeeklyPlan,
    user_id: UUID,
    days: list[NutritionWeeklyPlanDay],
    operation: str,
    *,
    physician_id: UUID | None = None,
) -> WeeklyPlanResponse:
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
        warning_codes=["PHYSICIAN_PLAN_EDIT" if physician_id else "USER_PLAN_EDIT"],
        input_signature=generation.input_signature,
        input_snapshot=dict(generation.input_snapshot),
        diagnostic_snapshot={"source_plan_id": str(plan.id), "operation": operation},
        planner_policy_version=generation.planner_policy_version,
        planner_version=generation.planner_version,
    )
    db.add(copied_generation)
    db.flush()
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
        warning_codes=list(
            set(plan.warning_codes + ["PHYSICIAN_PLAN_EDIT" if physician_id else "USER_PLAN_EDIT"])
        ),
        explanation_codes=list(plan.explanation_codes),
        weekly_cost_irr=sum(day.cost_irr for day in days),
        weekly_budget_irr=plan.weekly_budget_irr,
        budget_status=_budget_status(
            sum(day.cost_irr for day in days),
            plan.weekly_budget_irr,
            str(plan.input_snapshot.get("budget_mode", "strict")),
        ),
        days=days,
        nutrients=[
            _recalculated_nutrient(row, days, plan.input_snapshot) for row in plan.nutrients
        ],
        review=NutritionPlanPhysicianReview(
            status=NutritionPlanReviewStatus.IN_REVIEW
            if physician_id
            else NutritionPlanReviewStatus.PENDING,
            expected_plan_revision=revision,
            physician_user_id=physician_id,
            assigned_at=datetime.now(UTC) if physician_id else None,
            review_started_at=datetime.now(UTC) if physician_id else None,
            structured_change_summary=[{"operation": operation, "source_plan_id": str(plan.id)}],
        ),
    )
    if plan.review and plan.review.status in {
        NutritionPlanReviewStatus.PENDING,
        NutritionPlanReviewStatus.IN_REVIEW,
        NutritionPlanReviewStatus.AWAITING_LAB_INFORMATION,
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


def _budget_status(cost: int, budget: int, mode: str) -> NutritionPlanBudgetStatus:
    if cost <= budget:
        return NutritionPlanBudgetStatus.WITHIN_BUDGET
    if mode == "flexible" and cost <= round(budget * 1.1):
        return NutritionPlanBudgetStatus.FLEXIBLE_OVERAGE
    return NutritionPlanBudgetStatus.OVER_BUDGET


def _recalculated_nutrient(
    row: NutritionWeeklyPlanNutrient,
    days: list[NutritionWeeklyPlanDay],
    input_snapshot: dict[str, object],
) -> NutritionWeeklyPlanNutrient:
    code_map = {
        "goal_calories": "energy_kcal",
        "protein": "protein_g",
        "carbohydrate": "carbohydrate_g",
        "total_fat": "fat_g",
        "fibre": "fibre_g",
    }
    planned = sum(
        (
            Decimal(
                str(day.nutrient_totals.get(code_map.get(row.nutrient_code, row.nutrient_code), 0))
            )
            for day in days
        ),
        Decimal(),
    ) / Decimal(len(days))
    preferred = row.preferred_value
    minimums = input_snapshot.get("daily_minimums", {})
    maximums = input_snapshot.get("daily_maximums", {})
    upper_limits = input_snapshot.get("micronutrient_upper_limits", {})
    minimum = (
        Decimal(str(minimums[row.nutrient_code]))
        if isinstance(minimums, dict) and row.nutrient_code in minimums
        else None
    )
    maximum_source = (
        maximums if isinstance(maximums, dict) and row.nutrient_code in maximums else upper_limits
    )
    maximum = (
        Decimal(str(maximum_source[row.nutrient_code]))
        if isinstance(maximum_source, dict) and row.nutrient_code in maximum_source
        else None
    )
    if maximum is not None and planned > maximum:
        status, reasons = "above_applicable_limit", ["ABOVE_APPLICABLE_LIMIT"]
    elif minimum is not None and planned < minimum:
        status, reasons = "below_minimum", ["BELOW_MINIMUM"]
    elif preferred is not None and planned < preferred:
        status, reasons = (
            ("below_preferred_but_acceptable" if minimum is not None else "below_reference_target"),
            ["DIETARY_REFERENCE_GAP"],
        )
    else:
        status, reasons = "within_target", []
    limit = maximum if maximum is not None else minimum
    return NutritionWeeklyPlanNutrient(
        nutrient_code=row.nutrient_code,
        unit=row.unit,
        reference_kind=row.reference_kind,
        preferred_value=preferred,
        minimum_or_maximum_value=limit,
        planned_value=planned,
        difference_from_preferred=planned - preferred if preferred is not None else None,
        difference_from_limit=planned - limit if limit is not None else None,
        status=status,
        reason_codes=reasons,
        data_confidence=row.data_confidence,
        explanation_codes=["DIETARY_REFERENCE_GAP"] if "DIETARY_REFERENCE_GAP" in reasons else [],
    )


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
    meal = next(meal for day in plan.days for meal in day.meals if meal.id == meal_id)
    if meal.is_locked:
        raise PlanEditError("MEAL_LOCKED")
    days: list[NutritionWeeklyPlanDay] = []
    for day in plan.days:
        meals = [_copy_meal(meal) for meal in day.meals if meal.id != meal_id]
        days.append(
            NutritionWeeklyPlanDay(
                day_index=day.day_index,
                plan_date=day.plan_date,
                cost_irr=sum(meal.cost_irr for meal in meals),
                nutrient_totals=_sum_maps([meal.nutrient_totals for meal in meals]),
                meals=meals,
            )
        )
    return _create_revision(db, plan, user_id, days, "remove_meal", physician_id=physician_id)


def preview_replace_meal(
    db: Session, user_id: UUID, plan_id: UUID, meal_id: UUID, replacement_meal_id: UUID
) -> dict[str, object]:
    plan = owned_plan(db, user_id, plan_id)
    meals = {meal.id: meal for day in plan.days for meal in day.meals}
    target, replacement = meals.get(meal_id), meals.get(replacement_meal_id)
    if target is None or replacement is None:
        raise PlanEditError("MEAL_NOT_FOUND")
    if target.is_locked or replacement.is_locked:
        raise PlanEditError("MEAL_LOCKED")
    if target.slot_role != replacement.slot_role or target.id == replacement.id:
        raise PlanEditError("INCOMPATIBLE_MEAL_REPLACEMENT")
    return {
        "plan_id": plan.id,
        "expected_plan_revision_id": plan.id,
        "meal_id": target.id,
        "replacement_meal_id": replacement.id,
        "daily_delta": _delta(target.nutrient_totals, replacement.nutrient_totals),
        "weekly_cost_delta_irr": replacement.cost_irr - target.cost_irr,
        "requires_physician_review": True,
        "change_kind": "plan_defining",
    }


def confirm_replace_meal(
    db: Session,
    user_id: UUID,
    plan_id: UUID,
    expected_plan_revision_id: UUID,
    meal_id: UUID,
    replacement_meal_id: UUID,
) -> WeeklyPlanResponse:
    plan = owned_plan(db, user_id, plan_id, lock=True)
    _assert_editable(plan, expected_plan_revision_id)
    meals = {meal.id: meal for day in plan.days for meal in day.meals}
    target, replacement = meals.get(meal_id), meals.get(replacement_meal_id)
    if target is None or replacement is None:
        raise PlanEditError("MEAL_NOT_FOUND")
    if target.slot_role != replacement.slot_role or target.id == replacement.id:
        raise PlanEditError("INCOMPATIBLE_MEAL_REPLACEMENT")
    if target.is_locked or replacement.is_locked:
        raise PlanEditError("MEAL_LOCKED")
    days = [
        _copy_day(
            day,
            lambda meal: (
                _copy_meal(replacement, slot_index=target.slot_index)
                if meal.id == target.id
                else _copy_meal(meal)
            ),
        )
        for day in plan.days
    ]
    return _create_revision(db, plan, user_id, days, "replace_meal")


def preview_replace_food(
    db: Session,
    user_id: UUID,
    plan_id: UUID,
    meal_id: UUID,
    food_id: UUID,
    replacement_food_id: UUID,
) -> dict[str, object]:
    plan = owned_plan(db, user_id, plan_id)
    meal = next((meal for day in plan.days for meal in day.meals if meal.id == meal_id), None)
    if meal is None:
        raise PlanEditError("MEAL_NOT_FOUND")
    if meal.is_locked:
        raise PlanEditError("MEAL_LOCKED")
    target = next((food for food in meal.foods if food.food_id == food_id), None)
    replacement = next(
        (
            food
            for day in plan.days
            for candidate in day.meals
            for food in candidate.foods
            if food.food_id == replacement_food_id
        ),
        None,
    )
    if target is None or replacement is None or target.food_id == replacement.food_id:
        raise PlanEditError("FOOD_REPLACEMENT_NOT_FOUND")
    scaled = _scaled_food(replacement, target.grams)
    return {
        "plan_id": plan.id,
        "expected_plan_revision_id": plan.id,
        "meal_id": meal.id,
        "food_id": target.food_id,
        "replacement_food_id": replacement.food_id,
        "meal_delta": _delta(target.nutrient_snapshot, scaled.nutrient_snapshot),
        "cost_delta_irr": scaled.cost_irr - target.cost_irr,
        "requires_physician_review": True,
        "change_kind": "plan_defining",
    }


def confirm_replace_food(
    db: Session,
    user_id: UUID,
    plan_id: UUID,
    expected_plan_revision_id: UUID,
    meal_id: UUID,
    food_id: UUID,
    replacement_food_id: UUID,
    *,
    physician_id: UUID | None = None,
) -> WeeklyPlanResponse:
    plan = owned_plan(db, user_id, plan_id, lock=True)
    if physician_id is None:
        _assert_editable(plan, expected_plan_revision_id)
    elif plan.id != expected_plan_revision_id:
        raise PlanEditError("STALE_PLAN_REVISION")
    elif (
        plan.review is None
        or plan.review.physician_user_id != physician_id
        or plan.review.status != NutritionPlanReviewStatus.IN_REVIEW
    ):
        raise PlanEditError("REVIEW_ASSIGNED_TO_ANOTHER_PHYSICIAN")
    target_meal = next(
        (meal for day in plan.days for meal in day.meals if meal.id == meal_id), None
    )
    replacement = next(
        (
            food
            for day in plan.days
            for meal in day.meals
            for food in meal.foods
            if food.food_id == replacement_food_id
        ),
        None,
    )
    if target_meal is None or replacement is None:
        raise PlanEditError("FOOD_REPLACEMENT_NOT_FOUND")
    if target_meal.is_locked:
        raise PlanEditError("MEAL_LOCKED")
    if replacement is not None:
        source_meal = next(
            (meal for day in plan.days for meal in day.meals if replacement in meal.foods),
            None,
        )
        if source_meal is not None and source_meal.is_locked:
            raise PlanEditError("MEAL_LOCKED")
    target = next((food for food in target_meal.foods if food.food_id == food_id), None)
    if target is None or target.food_id == replacement.food_id:
        raise PlanEditError("FOOD_REPLACEMENT_NOT_FOUND")

    def transform(meal: NutritionWeeklyPlanMeal) -> NutritionWeeklyPlanMeal:
        if meal.id != target_meal.id:
            return _copy_meal(meal)
        foods = [
            _scaled_food(replacement, target.grams)
            if food.food_id == target.food_id
            else _copy_food(food)
            for food in meal.foods
        ]
        return NutritionWeeklyPlanMeal(
            catalogue_meal_id=meal.catalogue_meal_id,
            catalogue_meal_category=meal.catalogue_meal_category,
            slot_role=meal.slot_role,
            slot_index=meal.slot_index,
            target_distribution=dict(meal.target_distribution),
            nutrient_totals=_sum_maps([food.nutrient_snapshot for food in foods]),
            cost_irr=sum(food.cost_irr for food in foods),
            is_locked=False,
            foods=foods,
        )

    days = [_copy_day(day, transform) for day in plan.days]
    return _create_revision(
        db,
        plan,
        user_id,
        days,
        "replace_food",
        physician_id=physician_id,
    )


def partial_regenerate(
    db: Session,
    user_id: UUID,
    plan_id: UUID,
    expected_plan_revision_id: UUID,
    day_indexes: list[int],
) -> WeeklyPlanResponse:
    plan = owned_plan(db, user_id, plan_id, lock=True)
    _assert_editable(plan, expected_plan_revision_id)
    selected = set(day_indexes)
    if not selected or not selected.issubset(set(range(7))):
        raise PlanEditError("INVALID_DAY_SELECTION")
    source_by_key = {
        (day.day_index, meal.slot_role, meal.slot_index): meal
        for day in plan.days
        for meal in day.meals
    }

    def transform_for(day_index: int, meal: NutritionWeeklyPlanMeal) -> NutritionWeeklyPlanMeal:
        if day_index not in selected or meal.is_locked:
            return _copy_meal(meal)
        for offset in range(1, 7):
            candidate = source_by_key.get(
                ((day_index + offset) % 7, meal.slot_role, meal.slot_index)
            )
            if candidate is not None and candidate.id != meal.id:
                return _copy_meal(candidate, slot_index=meal.slot_index)
        return _copy_meal(meal)

    days = [
        _copy_day(day, lambda meal, index=day.day_index: transform_for(index, meal))
        for day in plan.days
    ]
    return _create_revision(db, plan, user_id, days, "partial_regeneration")


def _assert_editable(plan: NutritionWeeklyPlan, expected: UUID) -> None:
    if plan.id != expected:
        raise PlanEditError("STALE_PLAN_REVISION")
    if plan.generation and plan.generation.plan_role == NutritionPlanRole.IDEAL_REFERENCE.value:
        raise PlanEditError("IDEAL_REFERENCE_PLAN_CANNOT_BE_EDITED")
    if plan.review and plan.review.status == NutritionPlanReviewStatus.IN_REVIEW:
        raise PlanEditError("PLAN_REVIEW_IN_PROGRESS")


def _copy_day(day: NutritionWeeklyPlanDay, transform: Any) -> NutritionWeeklyPlanDay:
    meals = [transform(meal) for meal in day.meals]
    return NutritionWeeklyPlanDay(
        day_index=day.day_index,
        plan_date=day.plan_date,
        cost_irr=sum(meal.cost_irr for meal in meals),
        nutrient_totals=_sum_maps([meal.nutrient_totals for meal in meals]),
        meals=meals,
    )


def _delta(before: dict[str, object], after: dict[str, object]) -> dict[str, float]:
    keys = set(before) | set(after)
    return {
        key: float(Decimal(str(after.get(key, 0))) - Decimal(str(before.get(key, 0))))
        for key in keys
    }


def _float_map(values: dict[str, object]) -> dict[str, float]:
    return {key: float(str(value)) for key, value in values.items()}


def _scaled_food(food: NutritionWeeklyPlanFood, grams: Decimal) -> NutritionWeeklyPlanFood:
    ratio = grams / food.grams
    return NutritionWeeklyPlanFood(
        food_id=food.food_id,
        food_slug=food.food_slug,
        food_name_fa=food.food_name_fa,
        food_name_en=food.food_name_en,
        grams=grams,
        cost_irr=round(food.cost_irr * float(ratio)),
        nutrient_snapshot={
            key: str(Decimal(str(value)) * ratio) for key, value in food.nutrient_snapshot.items()
        },
        price_snapshot=dict(food.price_snapshot),
    )


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
    review = db.scalar(
        select(NutritionPlanPhysicianReview).where(NutritionPlanPhysicianReview.plan_id == plan_id)
    )
    if review is None or review.physician_user_id != physician_id:
        raise PlanEditError("REVIEW_ASSIGNED_TO_ANOTHER_PHYSICIAN")
    if review.status != NutritionPlanReviewStatus.IN_REVIEW:
        raise PlanEditError("REVIEW_NOT_IN_PROGRESS")
    return confirm_remove_meal(
        db,
        plan.user_id,
        plan_id,
        expected_plan_revision_id,
        meal_id,
        physician_id=physician_id,
    )


def physician_adjust_food_quantity(
    db: Session,
    physician_id: UUID,
    plan_id: UUID,
    expected_plan_revision_id: UUID,
    meal_id: UUID,
    food_id: UUID,
    grams: Decimal,
) -> WeeklyPlanResponse:
    try:
        require_physician(db, physician_id)
    except ClinicalError as error:
        raise PlanEditError("PHYSICIAN_ROLE_REQUIRED") from error
    plan = db.scalar(_query().where(NutritionWeeklyPlan.id == plan_id).with_for_update())
    if plan is None:
        raise PlanEditError("NUTRITION_PLAN_NOT_FOUND")
    if plan.id != expected_plan_revision_id:
        raise PlanEditError("STALE_PLAN_REVISION")
    if (
        plan.review is None
        or plan.review.physician_user_id != physician_id
        or plan.review.status != NutritionPlanReviewStatus.IN_REVIEW
    ):
        raise PlanEditError("REVIEW_ASSIGNED_TO_ANOTHER_PHYSICIAN")
    target_meal = next(
        (meal for day in plan.days for meal in day.meals if meal.id == meal_id),
        None,
    )
    if target_meal is None:
        raise PlanEditError("MEAL_NOT_FOUND")
    target_food = next((food for food in target_meal.foods if food.food_id == food_id), None)
    if target_food is None:
        raise PlanEditError("FOOD_REPLACEMENT_NOT_FOUND")

    def transform(meal: NutritionWeeklyPlanMeal) -> NutritionWeeklyPlanMeal:
        if meal.id != target_meal.id:
            return _copy_meal(meal)
        foods = [
            _scaled_food(food, grams) if food.food_id == target_food.food_id else _copy_food(food)
            for food in meal.foods
        ]
        return NutritionWeeklyPlanMeal(
            catalogue_meal_id=meal.catalogue_meal_id,
            catalogue_meal_category=meal.catalogue_meal_category,
            slot_role=meal.slot_role,
            slot_index=meal.slot_index,
            target_distribution=dict(meal.target_distribution),
            nutrient_totals=_sum_maps([food.nutrient_snapshot for food in foods]),
            cost_irr=sum(food.cost_irr for food in foods),
            is_locked=meal.is_locked,
            foods=foods,
        )

    days = [_copy_day(day, transform) for day in plan.days]
    return _create_revision(
        db,
        plan,
        plan.user_id,
        days,
        "adjust_food_quantity",
        physician_id=physician_id,
    )


def physician_replace_food(
    db: Session,
    physician_id: UUID,
    plan_id: UUID,
    expected_plan_revision_id: UUID,
    meal_id: UUID,
    food_id: UUID,
    replacement_food_id: UUID,
) -> WeeklyPlanResponse:
    try:
        require_physician(db, physician_id)
    except ClinicalError as error:
        raise PlanEditError("PHYSICIAN_ROLE_REQUIRED") from error
    user_id = db.scalar(
        select(NutritionWeeklyPlan.user_id).where(NutritionWeeklyPlan.id == plan_id)
    )
    if user_id is None:
        raise PlanEditError("NUTRITION_PLAN_NOT_FOUND")
    return confirm_replace_food(
        db,
        user_id,
        plan_id,
        expected_plan_revision_id,
        meal_id,
        food_id,
        replacement_food_id,
        physician_id=physician_id,
    )


def physician_plan(db: Session, physician_id: UUID, plan_id: UUID) -> WeeklyPlanResponse:
    try:
        require_physician(db, physician_id)
    except ClinicalError as error:
        raise PlanEditError("PHYSICIAN_ROLE_REQUIRED") from error
    plan = db.scalar(_query().where(NutritionWeeklyPlan.id == plan_id))
    if plan is None or plan.review is None:
        raise PlanEditError("NUTRITION_PLAN_NOT_FOUND")
    if plan.review.physician_user_id != physician_id:
        raise PlanEditError("REVIEW_ASSIGNED_TO_ANOTHER_PHYSICIAN")
    return weekly_plan_response(plan)


def physician_action(
    db: Session,
    physician_id: UUID,
    plan_id: UUID,
    expected_plan_revision_id: UUID,
    action: str,
    notes: str | None,
    internal_notes: str | None = None,
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
    if plan.review.physician_user_id not in {None, physician_id}:
        raise PlanEditError("REVIEW_ASSIGNED_TO_ANOTHER_PHYSICIAN")
    if action != "start_review" and plan.review.physician_user_id is None:
        raise PlanEditError("REVIEW_NOT_CLAIMED")
    if action != "start_review" and plan.review.physician_user_id != physician_id:
        raise PlanEditError("REVIEW_ASSIGNED_TO_ANOTHER_PHYSICIAN")
    plan.review.user_visible_notes = notes
    if internal_notes is not None:
        plan.review.internal_notes = internal_notes
    if action == "start_review":
        if plan.review.status not in {
            NutritionPlanReviewStatus.PENDING,
            NutritionPlanReviewStatus.CHANGES_REQUESTED,
        }:
            raise PlanEditError("INVALID_REVIEW_TRANSITION")
        plan.review.physician_user_id = physician_id
        plan.review.assigned_at = plan.review.assigned_at or now
        plan.review.status = NutritionPlanReviewStatus.IN_REVIEW
        plan.lifecycle_status = NutritionPlanLifecycleStatus.PHYSICIAN_REVIEW_IN_PROGRESS
        plan.review.review_started_at = now
    elif action == "approve":
        if plan.review.status != NutritionPlanReviewStatus.IN_REVIEW:
            raise PlanEditError("REVIEW_NOT_IN_PROGRESS")
        if (
            any(
                nutrient.status in {"below_minimum", "above_applicable_limit"}
                for nutrient in plan.nutrients
            )
            or plan.budget_status == NutritionPlanBudgetStatus.OVER_BUDGET
        ):
            raise PlanEditError("PLAN_HARD_INVARIANTS_FAILED")
        plan.review.status = NutritionPlanReviewStatus.APPROVED
        plan.review.reviewed_at = now
        if plan.start_date <= date.today():
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
        if not notes:
            raise PlanEditError("REVIEW_NOTES_REQUIRED")
        if plan.review.status not in {
            NutritionPlanReviewStatus.IN_REVIEW,
            NutritionPlanReviewStatus.AWAITING_LAB_INFORMATION,
        }:
            raise PlanEditError("REVIEW_NOT_IN_PROGRESS")
        plan.review.status = NutritionPlanReviewStatus.CHANGES_REQUESTED
        plan.lifecycle_status = NutritionPlanLifecycleStatus.CHANGES_REQUESTED
    elif action == "reject":
        if not notes:
            raise PlanEditError("REVIEW_NOTES_REQUIRED")
        if plan.review.status not in {
            NutritionPlanReviewStatus.IN_REVIEW,
            NutritionPlanReviewStatus.AWAITING_LAB_INFORMATION,
        }:
            raise PlanEditError("REVIEW_NOT_IN_PROGRESS")
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
