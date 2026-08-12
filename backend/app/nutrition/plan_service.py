from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.nutrition.enums import (
    FoodItemKind,
    FoodVerificationStatus,
    NutritionPlanBudgetStatus,
    NutritionPlanGenerationOutcome,
    NutritionPlanLifecycleStatus,
    NutritionPlanReviewStatus,
    NutritionTargetMetric,
    SafetyOutcome,
    Weekday,
)
from app.nutrition.estimate_service import create_estimate
from app.nutrition.exceptions import (
    GoalReselectionRequiredDomainError,
    NutritionProductModeError,
    NutritionTargetInfeasibleDomainError,
    StructuredExerciseRequiredError,
)
from app.nutrition.models import (
    NutritionCatalogueFood,
    NutritionCatalogueMeal,
    NutritionEstimate,
    NutritionEstimateMicronutrientTarget,
    NutritionEstimateTarget,
    NutritionFoodItem,
    NutritionPlanGeneration,
    NutritionPlanPhysicianReview,
    NutritionProfile,
    NutritionSafetyDecision,
    NutritionWeeklyPlan,
    NutritionWeeklyPlanDay,
    NutritionWeeklyPlanFood,
    NutritionWeeklyPlanMeal,
    NutritionWeeklyPlanNutrient,
)
from app.nutrition.planner_engine import (
    GenerationOutcome,
    PlannerFood,
    PlannerInput,
    PlannerMealIngredient,
    PlannerMealTemplate,
    PlannerResult,
    plan_week,
)
from app.nutrition.planner_policy import (
    DEFAULT_POLICY,
    PLANNER_POLICY_VERSION,
    PLANNER_VERSION,
)
from app.nutrition.price_overrides import effective_prices
from app.nutrition.schemas import (
    WeeklyPlanDayResponse,
    WeeklyPlanFoodResponse,
    WeeklyPlanGenerationResponse,
    WeeklyPlanHistoryItemResponse,
    WeeklyPlanMealResponse,
    WeeklyPlanNutrientResponse,
    WeeklyPlanResponse,
)
from app.nutrition.service import current_safety_decision

_HARD_EXCLUSION_KINDS = {
    FoodItemKind.NEVER_SUGGEST,
    FoodItemKind.REFUSED,
    FoodItemKind.ALLERGY,
    FoodItemKind.INTOLERANCE,
    FoodItemKind.RELIGIOUS_CULTURAL_EXCLUSION,
}
_TARGET_UNITS = {
    "goal_calories": "kcal/day",
    "protein": "g/day",
    "carbohydrate": "g/day",
    "total_fat": "g/day",
    "fibre": "g/day",
}
_WEEKDAY_INDEX = {
    Weekday.MONDAY: 0,
    Weekday.TUESDAY: 1,
    Weekday.WEDNESDAY: 2,
    Weekday.THURSDAY: 3,
    Weekday.FRIDAY: 4,
    Weekday.SATURDAY: 5,
    Weekday.SUNDAY: 6,
}


class WeeklyPlanNotFoundError(Exception):
    pass


class ActiveWeeklyPlanNotFoundError(Exception):
    pass


def generate_weekly_plan(db: Session, user_id: UUID) -> WeeklyPlanGenerationResponse:
    safety = current_safety_decision(db, user_id)
    profile = db.get(NutritionProfile, user_id)
    if safety.outcome in {
        SafetyOutcome.PHYSICIAN_MANUAL_PLAN_REQUIRED,
        SafetyOutcome.UNSUPPORTED_OR_HARD_BLOCKED,
    }:
        generation = _persist_generation(
            db,
            user_id=user_id,
            safety=safety,
            estimate=None,
            outcome=NutritionPlanGenerationOutcome.SAFETY_BLOCKED,
            reasons=(safety.outcome.value.upper(),),
            warnings=(),
            input_snapshot=_safety_snapshot(safety),
            diagnostics={"ordinary_automatic_plan_created": False},
        )
        return _generation_response(generation, None)
    if profile is None:
        generation = _persist_generation(
            db,
            user_id=user_id,
            safety=safety,
            estimate=None,
            outcome=NutritionPlanGenerationOutcome.FAILED,
            reasons=("NUTRITION_PROFILE_REQUIRED",),
            warnings=(),
            input_snapshot=_safety_snapshot(safety),
            diagnostics={},
        )
        return _generation_response(generation, None)

    try:
        estimate_response = create_estimate(db, user_id)
    except GoalReselectionRequiredDomainError:
        generation = _persist_generation(
            db,
            user_id=user_id,
            safety=safety,
            estimate=None,
            outcome=NutritionPlanGenerationOutcome.TARGET_INFEASIBLE,
            reasons=("GOAL_RESELECTION_REQUIRED",),
            warnings=(),
            input_snapshot=_safety_snapshot(safety),
            diagnostics={},
        )
        return _generation_response(generation, None)
    except NutritionTargetInfeasibleDomainError as error:
        generation = _persist_generation(
            db,
            user_id=user_id,
            safety=safety,
            estimate=None,
            outcome=NutritionPlanGenerationOutcome.TARGET_INFEASIBLE,
            reasons=error.reason_codes,
            warnings=(),
            input_snapshot=_safety_snapshot(safety),
            diagnostics={},
        )
        return _generation_response(generation, None)
    except (StructuredExerciseRequiredError, NutritionProductModeError) as error:
        reason = (
            "STRUCTURED_EXERCISE_REQUIRED"
            if isinstance(error, StructuredExerciseRequiredError)
            else "NUTRITION_PRODUCT_MODE_REQUIRED"
        )
        generation = _persist_generation(
            db,
            user_id=user_id,
            safety=safety,
            estimate=None,
            outcome=NutritionPlanGenerationOutcome.FAILED,
            reasons=(reason,),
            warnings=(),
            input_snapshot=_safety_snapshot(safety),
            diagnostics={},
        )
        return _generation_response(generation, None)
    estimate = _estimate_by_id(db, estimate_response.id)

    targets = _daily_targets(estimate.targets)
    micro_targets, upper_limits, micro_metadata = _micronutrient_targets(
        estimate.micronutrient_targets
    )
    food_items = db.scalars(
        select(NutritionFoodItem).where(NutritionFoodItem.user_id == user_id)
    ).all()
    exclusions = tuple(
        item.normalized_name for item in food_items if item.kind in _HARD_EXCLUSION_KINDS
    )
    liked_food_ids = tuple(
        str(item.catalogue_food_id)
        for item in food_items
        if item.kind is FoodItemKind.FAVOURITE and item.catalogue_food_id is not None
    )
    disliked_food_ids = tuple(
        str(item.catalogue_food_id)
        for item in food_items
        if item.kind is FoodItemKind.DISLIKED and item.catalogue_food_id is not None
    )
    foods, price_snapshot, food_manifest = _planner_foods(db)
    meal_templates, meal_manifest = _planner_meal_templates(db)
    food_manifest["meals"] = meal_manifest
    minimums, maximums = _daily_limits(estimate.targets)
    weekly_budget = profile.individual_monthly_food_budget_irr * 12 // 52
    input_snapshot: dict[str, object] = {
        "estimate_id": str(estimate.id),
        "estimate_revision": estimate.revision,
        "safety_decision_id": str(safety.id),
        "safety_outcome": safety.outcome.value,
        "safety_reason_codes": [reason.code for reason in safety.reasons],
        "medical_condition_policy_version": safety.medical_condition_policy_version,
        "main_meal_count_bucket": profile.main_meal_count_bucket.value,
        "snack_count_bucket": profile.snack_count_bucket.value,
        "main_meals_per_day": profile.effective_main_meal_slots,
        "snacks_per_day": profile.effective_snack_slots,
        "weekly_budget_irr": weekly_budget,
        "budget_mode": profile.budget_style.value,
        "daily_targets": _json_decimal_map(targets),
        "daily_minimums": _json_decimal_map(minimums),
        "daily_maximums": _json_decimal_map(maximums),
        "micronutrient_targets": _json_decimal_map(micro_targets),
        "micronutrient_upper_limits": _json_decimal_map(upper_limits),
        "micronutrient_reference_rows": micro_metadata,
        "hard_exclusions": list(exclusions),
        "liked_food_ids": list(liked_food_ids),
        "disliked_food_ids": list(disliked_food_ids),
        "dietary_pattern": profile.dietary_pattern.value,
        "maximum_meal_repetition_per_week": profile.maximum_meal_repetition_per_week,
        "meal_distribution_policy_version": "meal-distribution-v1",
        "budget_formula_version": "annualized-monthly-times-12-divided-52-v1",
        "meal_catalogue_template_ids": [item.meal_id for item in meal_templates],
    }
    result = plan_week(
        PlannerInput(
            daily_targets=targets,
            micronutrient_targets=micro_targets,
            micronutrient_upper_limits=upper_limits,
            daily_minimums=minimums,
            daily_maximums=maximums,
            main_meals_per_day=profile.effective_main_meal_slots,
            snacks_per_day=profile.effective_snack_slots,
            weekly_budget_irr=weekly_budget,
            budget_mode=profile.budget_style.value,
            excluded_terms=exclusions,
            liked_food_ids=liked_food_ids,
            disliked_food_ids=disliked_food_ids,
            dietary_pattern=profile.dietary_pattern.value,
            maximum_meal_repetition_per_week=profile.maximum_meal_repetition_per_week,
        ),
        foods,
        meal_templates,
    )
    outcome = NutritionPlanGenerationOutcome(result.outcome.value)
    generation = _persist_generation(
        db,
        user_id=user_id,
        safety=safety,
        estimate=estimate,
        outcome=outcome,
        reasons=result.reason_codes,
        warnings=result.warning_codes,
        input_snapshot=input_snapshot,
        diagnostics={
            "candidate_count": len(foods),
            "meal_template_count": len(meal_templates),
            "weekly_cost_irr": str(result.weekly_cost_irr),
            "budget_status": result.budget_status,
        },
        commit=False,
    )
    if result.outcome is not GenerationOutcome.SUCCESS:
        db.commit()
        db.refresh(generation)
        return _generation_response(generation, None)

    plan = _persist_successful_plan(
        db,
        generation=generation,
        profile=profile,
        estimate=estimate,
        safety=safety,
        result=result,
        input_snapshot=input_snapshot,
        price_snapshot=price_snapshot,
        food_manifest=food_manifest,
        micro_metadata=micro_metadata,
    )
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    return _generation_response(generation, _load_plan(db, plan.id))


def latest_weekly_plan(db: Session, user_id: UUID) -> WeeklyPlanResponse:
    plan = db.scalar(
        _plan_query()
        .where(
            NutritionWeeklyPlan.user_id == user_id,
            NutritionWeeklyPlan.is_user_visible.is_(True),
        )
        .order_by(NutritionWeeklyPlan.revision.desc())
    )
    if plan is None:
        raise WeeklyPlanNotFoundError
    return weekly_plan_response(plan)


def active_weekly_plan(db: Session, user_id: UUID) -> WeeklyPlanResponse:
    due = db.scalar(
        _plan_query()
        .where(
            NutritionWeeklyPlan.user_id == user_id,
            NutritionWeeklyPlan.lifecycle_status == NutritionPlanLifecycleStatus.PHYSICIAN_APPROVED,
            NutritionWeeklyPlan.start_date <= date.today(),
        )
        .order_by(NutritionWeeklyPlan.revision.desc())
        .limit(1)
        .with_for_update()
    )
    if due is not None and due.review and due.review.status == NutritionPlanReviewStatus.APPROVED:
        for current in db.scalars(
            select(NutritionWeeklyPlan).where(
                NutritionWeeklyPlan.user_id == user_id,
                NutritionWeeklyPlan.id != due.id,
                NutritionWeeklyPlan.lifecycle_status == NutritionPlanLifecycleStatus.ACTIVE,
            )
        ):
            current.lifecycle_status = NutritionPlanLifecycleStatus.ARCHIVED
        due.lifecycle_status = NutritionPlanLifecycleStatus.ACTIVE
        db.commit()
    plan = db.scalar(
        _plan_query()
        .where(
            NutritionWeeklyPlan.user_id == user_id,
            NutritionWeeklyPlan.lifecycle_status == NutritionPlanLifecycleStatus.ACTIVE,
        )
        .order_by(NutritionWeeklyPlan.revision.desc())
    )
    if plan is None:
        raise ActiveWeeklyPlanNotFoundError
    return weekly_plan_response(plan)


def weekly_plan_by_id(db: Session, user_id: UUID, plan_id: UUID) -> WeeklyPlanResponse:
    plan = db.scalar(
        _plan_query().where(
            NutritionWeeklyPlan.id == plan_id,
            NutritionWeeklyPlan.user_id == user_id,
            NutritionWeeklyPlan.is_user_visible.is_(True),
        )
    )
    if plan is None:
        raise WeeklyPlanNotFoundError
    return weekly_plan_response(plan)


def weekly_plan_history(db: Session, user_id: UUID) -> list[WeeklyPlanHistoryItemResponse]:
    plans = db.scalars(
        select(NutritionWeeklyPlan)
        .where(NutritionWeeklyPlan.user_id == user_id)
        .options(selectinload(NutritionWeeklyPlan.review))
        .order_by(NutritionWeeklyPlan.revision.desc())
    ).all()
    return [
        WeeklyPlanHistoryItemResponse(
            id=plan.id,
            revision=plan.revision,
            lifecycle_status=plan.lifecycle_status.value,
            review_status=plan.review.status.value if plan.review else "missing",
            weekly_cost_irr=plan.weekly_cost_irr,
            weekly_budget_irr=plan.weekly_budget_irr,
            budget_status=plan.budget_status.value,
            created_at=plan.created_at,
        )
        for plan in plans
    ]


def _persist_generation(
    db: Session,
    *,
    user_id: UUID,
    safety: NutritionSafetyDecision,
    estimate: NutritionEstimate | None,
    outcome: NutritionPlanGenerationOutcome,
    reasons: tuple[str, ...],
    warnings: tuple[str, ...],
    input_snapshot: dict[str, object],
    diagnostics: dict[str, object],
    commit: bool = True,
) -> NutritionPlanGeneration:
    signature = sha256(
        json.dumps(input_snapshot, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    generation = NutritionPlanGeneration(
        user_id=user_id,
        estimate_id=estimate.id if estimate else None,
        safety_decision_id=safety.id,
        outcome=outcome,
        reason_codes=list(reasons),
        warning_codes=list(warnings),
        input_signature=signature,
        input_snapshot=input_snapshot,
        diagnostic_snapshot=diagnostics,
        planner_policy_version=PLANNER_POLICY_VERSION,
        planner_version=PLANNER_VERSION,
    )
    db.add(generation)
    if commit:
        db.commit()
        db.refresh(generation)
    else:
        db.flush()
    return generation


def _safety_snapshot(safety: NutritionSafetyDecision) -> dict[str, object]:
    return {
        "safety_decision_id": str(safety.id),
        "safety_outcome": safety.outcome.value,
        "safety_reason_codes": [reason.code for reason in safety.reasons],
        "medical_condition_policy_version": safety.medical_condition_policy_version,
    }


def _persist_successful_plan(
    db: Session,
    *,
    generation: NutritionPlanGeneration,
    profile: NutritionProfile,
    estimate: NutritionEstimate,
    safety: NutritionSafetyDecision,
    result: PlannerResult,
    input_snapshot: dict[str, object],
    price_snapshot: dict[str, object],
    food_manifest: dict[str, object],
    micro_metadata: dict[str, dict[str, object]],
) -> NutritionWeeklyPlan:
    latest_revision = db.scalar(
        select(NutritionWeeklyPlan.revision)
        .where(NutritionWeeklyPlan.user_id == profile.user_id)
        .order_by(NutritionWeeklyPlan.revision.desc())
        .limit(1)
    )
    start_date = _next_weekday(date.today(), profile.preferred_plan_start_day)
    plan_revision = (latest_revision or 0) + 1
    plan = NutritionWeeklyPlan(
        user_id=profile.user_id,
        generation_id=generation.id,
        estimate_id=estimate.id,
        safety_decision_id=safety.id,
        revision=plan_revision,
        lifecycle_status=NutritionPlanLifecycleStatus.PENDING_PHYSICIAN_REVIEW,
        is_user_visible=True,
        start_date=start_date,
        planner_policy_version=PLANNER_POLICY_VERSION,
        planner_version=PLANNER_VERSION,
        scientific_policy_version=estimate.policy_version,
        formula_version=estimate.formula_version,
        food_data_manifest=food_manifest,
        input_snapshot=input_snapshot,
        price_snapshot=price_snapshot,
        repair_snapshot=[
            {
                "nutrient_code": action.nutrient_code,
                "food_slug": action.food_slug,
                "grams_added": str(action.grams_added),
                "day_index": action.day_index,
                "reason_code": action.reason_code,
            }
            for action in result.repair_actions
        ],
        warning_codes=list(result.warning_codes),
        explanation_codes=["DETERMINISTIC_PLAN", "PHYSICIAN_REVIEW_REQUIRED"],
        weekly_cost_irr=int(result.weekly_cost_irr),
        weekly_budget_irr=profile.individual_monthly_food_budget_irr * 12 // 52,
        budget_status=NutritionPlanBudgetStatus(result.budget_status),
        days=[
            NutritionWeeklyPlanDay(
                day_index=day.day_index,
                plan_date=start_date + timedelta(days=day.day_index),
                cost_irr=int(day.cost_irr),
                nutrient_totals=_json_nutrient_pairs(day.nutrients),
                meals=[
                    NutritionWeeklyPlanMeal(
                        catalogue_meal_id=UUID(meal.template_id),
                        catalogue_meal_category=meal.template_category,
                        slot_role=meal.role,
                        slot_index=meal.slot_index,
                        target_distribution=_meal_target_distribution(
                            input_snapshot, meal.role, profile
                        ),
                        nutrient_totals=_json_nutrient_pairs(meal.nutrients),
                        cost_irr=int(meal.cost_irr),
                        foods=[
                            NutritionWeeklyPlanFood(
                                food_id=UUID(food.food_id),
                                food_slug=food.slug,
                                food_name_fa=food.name_fa,
                                food_name_en=food.name_en,
                                grams=food.grams,
                                cost_irr=int(food.cost_irr),
                                nutrient_snapshot=_json_nutrient_pairs(food.nutrients),
                                price_snapshot=_food_price_snapshot(price_snapshot, food.food_id),
                            )
                            for food in meal.foods
                        ],
                    )
                    for meal in day.meals
                ],
            )
            for day in result.days
        ],
        nutrients=[
            NutritionWeeklyPlanNutrient(
                nutrient_code=code,
                unit=_nutrient_unit(code, micro_metadata),
                reference_kind=_reference_kind(code, micro_metadata),
                preferred_value=comparison.preferred,
                minimum_or_maximum_value=comparison.minimum_or_maximum,
                planned_value=comparison.planned,
                difference_from_preferred=comparison.difference_from_preferred,
                difference_from_limit=comparison.difference_from_limit,
                status=comparison.status,
                reason_codes=list(comparison.reason_codes),
                data_confidence=comparison.data_confidence,
                explanation_codes=(
                    ["DIETARY_REFERENCE_GAP"]
                    if comparison.status
                    in {
                        "below_reference_target",
                        "below_preferred_but_acceptable",
                    }
                    else []
                ),
            )
            for code, comparison in sorted((result.nutrient_comparisons or {}).items())
        ],
        review=NutritionPlanPhysicianReview(
            status=NutritionPlanReviewStatus.PENDING,
            expected_plan_revision=plan_revision,
        ),
    )
    db.add(plan)
    db.flush()
    return plan


def _planner_foods(
    db: Session,
) -> tuple[tuple[PlannerFood, ...], dict[str, object], dict[str, object]]:
    foods = db.scalars(
        select(NutritionCatalogueFood)
        .where(NutritionCatalogueFood.verification_status == FoodVerificationStatus.VERIFIED)
        .options(
            selectinload(NutritionCatalogueFood.roles),
            selectinload(NutritionCatalogueFood.compositions),
        )
        .order_by(NutritionCatalogueFood.slug)
    ).all()
    references = effective_prices(
        db,
        [food.id for food in foods],
        maximum_age_hours=DEFAULT_POLICY.maximum_price_age_hours,
    )
    candidates: list[PlannerFood] = []
    snapshots: list[dict[str, object]] = []
    manifest: list[dict[str, object]] = []
    for food in foods:
        reference = references.get(food.id)
        if reference is None or reference.canonical_unit != "TOMAN_PER_KG":
            continue
        price_irr_per_gram = reference.reference_price_toman * Decimal("10") / Decimal("1000")
        candidates.append(
            PlannerFood(
                food_id=str(food.id),
                slug=food.slug,
                name_fa=food.name_fa,
                name_en=food.name_en,
                roles=tuple(sorted(role.role.value for role in food.roles)),
                nutrients_per_100g={
                    composition.nutrient_code: composition.value_per_100g
                    for composition in food.compositions
                },
                price_irr_per_gram=price_irr_per_gram,
                price_reference_id=reference.reference_id,
                dietary_patterns=tuple(food.dietary_patterns),
            )
        )
        snapshots.append(
            {
                "food_id": str(food.id),
                "reference_id": reference.reference_id,
                "reference_price_toman": str(reference.reference_price_toman),
                "canonical_unit": reference.canonical_unit,
                "price_irr_per_gram": str(price_irr_per_gram),
                "sample_count": reference.sample_count,
                "confidence": reference.confidence,
                "accepted_at": reference.accepted_at.isoformat(),
                "source": reference.source,
                "freshness_policy_hours": DEFAULT_POLICY.maximum_price_age_hours,
            }
        )
        manifest.append(
            {
                "food_id": str(food.id),
                "slug": food.slug,
                "source_name": food.source_name,
                "source_reference": food.source_reference,
                "source_food_id": food.source_food_id,
            }
        )
    return (
        tuple(candidates),
        {"currency": "IRR", "references": snapshots},
        {"foods": manifest},
    )


def _planner_meal_templates(
    db: Session,
) -> tuple[tuple[PlannerMealTemplate, ...], list[dict[str, object]]]:
    meals = db.scalars(
        select(NutritionCatalogueMeal)
        .where(NutritionCatalogueMeal.verification_status == FoodVerificationStatus.VERIFIED)
        .options(selectinload(NutritionCatalogueMeal.items))
        .order_by(NutritionCatalogueMeal.category, NutritionCatalogueMeal.id)
    ).all()
    templates = tuple(
        PlannerMealTemplate(
            meal_id=str(meal.id),
            name_fa=meal.name_fa,
            name_en=meal.name_en,
            category=meal.category.value,
            items=tuple(
                PlannerMealIngredient(
                    food_id=str(item.food_id),
                    reference_grams=item.reference_grams,
                    min_grams=item.min_grams,
                    max_grams=item.max_grams,
                    is_required=item.is_required,
                    functional_role=(
                        item.functional_role.value if item.functional_role is not None else None
                    ),
                )
                for item in meal.items
            ),
        )
        for meal in meals
    )
    return templates, [
        {
            "meal_id": template.meal_id,
            "category": template.category,
            "ingredient_bounds": [
                {
                    "food_id": item.food_id,
                    "reference_grams": str(item.reference_grams),
                    "min_grams": str(item.min_grams),
                    "max_grams": str(item.max_grams),
                    "is_required": item.is_required,
                    "functional_role": item.functional_role,
                }
                for item in template.items
            ],
        }
        for template in templates
    ]


def _daily_targets(rows: list[NutritionEstimateTarget]) -> dict[str, Decimal]:
    by_metric = {row.metric: row for row in rows}

    def selected(metric: NutritionTargetMetric) -> Decimal:
        row = by_metric[metric]
        if row.preferred_value is not None:
            return row.preferred_value
        if row.minimum_value is not None and row.preferred_maximum_value is not None:
            return (row.minimum_value + row.preferred_maximum_value) / Decimal("2")
        if row.minimum_value is not None and row.maximum_value is not None:
            return (row.minimum_value + row.maximum_value) / Decimal("2")
        if row.minimum_value is not None:
            return row.minimum_value
        raise ValueError(f"No usable target for {metric.value}")

    return {
        "goal_calories": selected(NutritionTargetMetric.GOAL_CALORIES),
        "protein": selected(NutritionTargetMetric.PROTEIN),
        "carbohydrate": selected(NutritionTargetMetric.CARBOHYDRATE),
        "total_fat": selected(NutritionTargetMetric.TOTAL_FAT),
        "fibre": selected(NutritionTargetMetric.FIBRE),
    }


def _daily_limits(
    rows: list[NutritionEstimateTarget],
) -> tuple[dict[str, Decimal], dict[str, Decimal]]:
    minimums: dict[str, Decimal] = {}
    maximums: dict[str, Decimal] = {}
    metric_names = {
        NutritionTargetMetric.PROTEIN: "protein",
        NutritionTargetMetric.CARBOHYDRATE: "carbohydrate",
        NutritionTargetMetric.TOTAL_FAT: "total_fat",
        NutritionTargetMetric.FIBRE: "fibre",
        NutritionTargetMetric.FREE_SUGAR: "free_sugar",
        NutritionTargetMetric.ADDED_SUGAR: "added_sugar",
        NutritionTargetMetric.SATURATED_FAT: "saturated_fat",
        NutritionTargetMetric.TRANS_FAT: "trans_fat",
        NutritionTargetMetric.SODIUM: "sodium",
    }
    for row in rows:
        name = metric_names.get(row.metric)
        if name is None:
            continue
        if row.minimum_value is not None:
            minimums[name] = row.minimum_value
        maximum = row.preferred_maximum_value or row.maximum_value
        if maximum is not None:
            maximums[name] = maximum
    return minimums, maximums


def _micronutrient_targets(
    rows: list[NutritionEstimateMicronutrientTarget],
) -> tuple[dict[str, Decimal], dict[str, Decimal], dict[str, dict[str, object]]]:
    targets: dict[str, Decimal] = {}
    upper_limits: dict[str, Decimal] = {}
    metadata: dict[str, dict[str, object]] = {}
    for row in rows:
        food_code = _composition_code(row.nutrient_code, row.unit)
        targets[food_code] = row.target_value
        if row.upper_limit_value is not None and row.upper_limit_scope == "total_intake":
            upper_limits[food_code] = row.upper_limit_value
        metadata[food_code] = {
            "nutrient_code": row.nutrient_code,
            "unit": row.unit,
            "reference_kind": row.reference_kind,
            "policy_version": row.policy_version,
            "upper_limit_scope": row.upper_limit_scope,
            "aggregation_window": row.aggregation_window,
        }
    return targets, upper_limits, metadata


def _composition_code(code: str, unit: str) -> str:
    suffix = unit.casefold().replace("µ", "u").replace("μ", "u")
    return code if code.endswith(f"_{suffix}") else f"{code}_{suffix}"


def _estimate_by_id(db: Session, estimate_id: UUID) -> NutritionEstimate:
    estimate = db.scalar(
        select(NutritionEstimate)
        .where(NutritionEstimate.id == estimate_id)
        .options(
            selectinload(NutritionEstimate.targets),
            selectinload(NutritionEstimate.micronutrient_targets),
        )
    )
    if estimate is None:
        raise ValueError("Estimate disappeared after creation")
    return estimate


def _plan_query() -> Select[tuple[NutritionWeeklyPlan]]:
    return select(NutritionWeeklyPlan).options(
        selectinload(NutritionWeeklyPlan.review),
        selectinload(NutritionWeeklyPlan.nutrients),
        selectinload(NutritionWeeklyPlan.days)
        .selectinload(NutritionWeeklyPlanDay.meals)
        .selectinload(NutritionWeeklyPlanMeal.foods),
        selectinload(NutritionWeeklyPlan.days)
        .selectinload(NutritionWeeklyPlanDay.meals)
        .selectinload(NutritionWeeklyPlanMeal.catalogue_meal),
    )


def _load_plan(db: Session, plan_id: UUID) -> NutritionWeeklyPlan:
    plan = db.scalar(_plan_query().where(NutritionWeeklyPlan.id == plan_id))
    if plan is None:
        raise WeeklyPlanNotFoundError
    return plan


def weekly_plan_response(plan: NutritionWeeklyPlan) -> WeeklyPlanResponse:
    review_status = plan.review.status.value if plan.review else "missing"
    return WeeklyPlanResponse(
        id=plan.id,
        revision=plan.revision,
        lifecycle_status=plan.lifecycle_status.value,
        is_user_visible=plan.is_user_visible,
        physician_approved=(
            plan.lifecycle_status
            in {
                NutritionPlanLifecycleStatus.PHYSICIAN_APPROVED,
                NutritionPlanLifecycleStatus.ACTIVE,
            }
            and review_status == NutritionPlanReviewStatus.APPROVED.value
        ),
        review_status=review_status,
        physician_approved_at=(
            plan.review.reviewed_at
            if plan.review and plan.review.status == NutritionPlanReviewStatus.APPROVED
            else None
        ),
        physician_display_name=(
            "Fitsho physician"
            if plan.review and plan.review.status == NutritionPlanReviewStatus.APPROVED
            else None
        ),
        physician_user_visible_notes=plan.review.user_visible_notes if plan.review else None,
        physician_change_summary=(plan.review.structured_change_summary if plan.review else []),
        supersedes_plan_id=plan.supersedes_plan_id,
        start_date=plan.start_date,
        planner_policy_version=plan.planner_policy_version,
        planner_version=plan.planner_version,
        scientific_policy_version=plan.scientific_policy_version,
        formula_version=plan.formula_version,
        weekly_cost_irr=plan.weekly_cost_irr,
        weekly_budget_irr=plan.weekly_budget_irr,
        budget_status=plan.budget_status.value,
        warning_codes=plan.warning_codes,
        explanation_codes=plan.explanation_codes,
        input_snapshot=plan.input_snapshot,
        price_snapshot=plan.price_snapshot,
        food_data_manifest=plan.food_data_manifest,
        repair_actions=plan.repair_snapshot,
        nutrients={
            nutrient.nutrient_code: WeeklyPlanNutrientResponse(
                nutrient_code=nutrient.nutrient_code,
                unit=nutrient.unit,
                reference_kind=nutrient.reference_kind,
                preferred=_float(nutrient.preferred_value),
                minimum_or_maximum=_float(nutrient.minimum_or_maximum_value),
                planned=float(nutrient.planned_value),
                difference_from_preferred=_float(nutrient.difference_from_preferred),
                difference_from_limit=_float(nutrient.difference_from_limit),
                status=nutrient.status,
                reason_codes=nutrient.reason_codes,
                data_confidence=nutrient.data_confidence,
                explanation_codes=nutrient.explanation_codes,
            )
            for nutrient in plan.nutrients
        },
        days=[
            WeeklyPlanDayResponse(
                day_index=day.day_index,
                plan_date=day.plan_date,
                nutrient_totals=_float_map(day.nutrient_totals),
                cost_irr=day.cost_irr,
                meals=[
                    WeeklyPlanMealResponse(
                        id=meal.id,
                        catalogue_meal_id=meal.catalogue_meal_id,
                        catalogue_meal_category=meal.catalogue_meal_category,
                        name_fa=(meal.catalogue_meal.name_fa if meal.catalogue_meal else None),
                        name_en=(meal.catalogue_meal.name_en if meal.catalogue_meal else None),
                        meal_code=(meal.catalogue_meal.code if meal.catalogue_meal else None),
                        image_url=(meal.catalogue_meal.image_path if meal.catalogue_meal else None),
                        slot_role=meal.slot_role.value,
                        slot_index=meal.slot_index,
                        target_distribution=_float_map(meal.target_distribution),
                        nutrient_totals=_float_map(meal.nutrient_totals),
                        cost_irr=meal.cost_irr,
                        is_locked=meal.is_locked,
                        foods=[
                            WeeklyPlanFoodResponse(
                                food_id=food.food_id,
                                slug=food.food_slug,
                                name_fa=food.food_name_fa,
                                name_en=food.food_name_en,
                                grams=float(food.grams),
                                cost_irr=food.cost_irr,
                                nutrients=_float_map(food.nutrient_snapshot),
                            )
                            for food in meal.foods
                        ],
                    )
                    for meal in day.meals
                ],
            )
            for day in plan.days
        ],
        created_at=plan.created_at,
    )


def _generation_response(
    generation: NutritionPlanGeneration, plan: NutritionWeeklyPlan | None
) -> WeeklyPlanGenerationResponse:
    return WeeklyPlanGenerationResponse(
        generation_id=generation.id,
        outcome=generation.outcome.value,
        reason_codes=generation.reason_codes,
        warning_codes=generation.warning_codes,
        plan=weekly_plan_response(plan) if plan else None,
    )


def _meal_target_distribution(
    snapshot: dict[str, object], role: str, profile: NutritionProfile
) -> dict[str, str]:
    raw_targets = snapshot["daily_targets"]
    if not isinstance(raw_targets, dict):
        return {}
    if role == "snack" and profile.effective_snack_slots:
        share = Decimal("0.15") / Decimal(profile.effective_snack_slots)
    else:
        share = (Decimal("0.85") if profile.effective_snack_slots else Decimal("1")) / Decimal(
            profile.effective_main_meal_slots
        )
    return {str(code): str(Decimal(str(value)) * share) for code, value in raw_targets.items()}


def _food_price_snapshot(snapshot: dict[str, object], food_id: str) -> dict[str, object]:
    references = snapshot.get("references", [])
    if isinstance(references, list):
        for reference in references:
            if isinstance(reference, dict) and reference.get("food_id") == food_id:
                return dict(reference)
    return {"food_id": food_id, "status": "unavailable"}


def _next_weekday(today: date, preferred: Weekday) -> date:
    delta = (_WEEKDAY_INDEX[preferred] - today.weekday()) % 7
    return today + timedelta(days=delta)


def _json_decimal_map(values: dict[str, Decimal]) -> dict[str, str]:
    return {key: str(value) for key, value in sorted(values.items())}


def _json_nutrient_pairs(values: tuple[tuple[str, Decimal], ...]) -> dict[str, str]:
    return {key: str(value) for key, value in values}


def _float_map(values: dict[str, object]) -> dict[str, float]:
    result: dict[str, float] = {}
    for key, value in values.items():
        if not isinstance(value, (str, int, float, Decimal)):
            raise TypeError(f"Nutrient value for {key} is not numeric")
        result[key] = float(value)
    return result


def _float(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def _nutrient_unit(code: str, metadata: dict[str, dict[str, object]]) -> str:
    if code in metadata:
        return str(metadata[code]["unit"])
    return _TARGET_UNITS.get(code, "unknown")


def _reference_kind(code: str, metadata: dict[str, dict[str, object]]) -> str | None:
    return str(metadata[code]["reference_kind"]) if code in metadata else None
