"""Preconstruction program cost estimation based on live prices and user needs."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from app.nutrition.enums import (
    MainMealCountBucket,
    MealCategory,
    NutritionBudgetTier,
    SnackCountBucket,
)
from app.nutrition.models import NutritionProgram
from app.nutrition.planner_policy import resolve_budget_tier
from app.nutrition.program_adaptation import adapt_program

if TYPE_CHECKING:
    from app.nutrition.planner_engine import PlannerFood, PlannerMealTemplate


@dataclass(frozen=True)
class ProgramCostEstimate:
    program_code: str
    estimated_monthly_cost_irr: Decimal
    minimum_adapted_monthly_cost_irr: Decimal | None
    effective_budget_tier: str
    price_coverage_complete: bool
    estimate_confidence: str
    reason_codes: tuple[str, ...]


def template_cost_and_kcal(
    template: PlannerMealTemplate,
    foods_by_id: dict[str, PlannerFood],
) -> tuple[Decimal, Decimal, bool]:
    """Return (reference_cost_irr, reference_kcal, price_coverage_complete)."""
    total_cost = Decimal("0")
    total_kcal = Decimal("0")
    coverage_complete = True

    for item in template.items:
        food = foods_by_id.get(item.food_id)
        if (
            food is None
            or food.price_irr_per_gram is None
            or food.price_irr_per_gram <= Decimal("0")
        ):
            coverage_complete = False
        else:
            total_cost += item.reference_grams * food.price_irr_per_gram

        if food is not None:
            energy_100g = food.nutrients_per_100g.get("energy_kcal", Decimal("0"))
            total_kcal += (energy_100g * item.reference_grams) / Decimal("100")
        else:
            coverage_complete = False

    return total_cost, total_kcal, coverage_complete


def estimate_program_cost(
    program: NutritionProgram,
    *,
    main_meal_slots: int = 3,
    snack_slots: int = 1,
    daily_kcal: Decimal = Decimal("2200"),
    meal_templates_by_id: dict[str, PlannerMealTemplate] | None = None,
    foods_by_id: dict[str, PlannerFood] | None = None,
    user_monthly_budget_irr: int | None = None,
    snack_energy_share: Decimal = Decimal("0.15"),
) -> ProgramCostEstimate:
    """Derive user-tailored runtime monthly cost for an adapted program."""
    if not meal_templates_by_id or not foods_by_id:
        tier = NutritionBudgetTier.NORMAL.value
        reasons = ("PROGRAM_COST_PREFLIGHT_UNCERTAIN",)
        return ProgramCostEstimate(
            program_code=program.code,
            estimated_monthly_cost_irr=Decimal("150000000"),
            minimum_adapted_monthly_cost_irr=None,
            effective_budget_tier=tier,
            price_coverage_complete=False,
            estimate_confidence="uncertain",
            reason_codes=reasons,
        )

    if main_meal_slots <= 2:
        main_bucket = MainMealCountBucket.TWO
    elif main_meal_slots == 3:
        main_bucket = MainMealCountBucket.THREE
    else:
        main_bucket = MainMealCountBucket.FOUR_OR_MORE

    if snack_slots <= 0:
        snack_bucket = SnackCountBucket.ZERO
    elif snack_slots == 1:
        snack_bucket = SnackCountBucket.ONE
    elif snack_slots == 2:
        snack_bucket = SnackCountBucket.TWO
    else:
        snack_bucket = SnackCountBucket.THREE_OR_MORE

    effective_snack_share = snack_energy_share if snack_slots > 0 else Decimal("0")
    main_target_kcal = (
        daily_kcal * (Decimal("1") - effective_snack_share) / Decimal(max(main_meal_slots, 1))
    )
    snack_target_kcal = (
        daily_kcal * effective_snack_share / Decimal(snack_slots)
        if snack_slots > 0
        else Decimal("0")
    )

    adapted_week = adapt_program(program, main_bucket, snack_bucket)

    weekly_cost = Decimal("0")
    price_coverage_complete = True

    # Precalculate template costs and category minimums
    template_costs: dict[str, tuple[Decimal, Decimal, bool]] = {}
    category_cheapest_rate: dict[str, Decimal] = {}

    for t_id, template in meal_templates_by_id.items():
        cost, kcal, complete = template_cost_and_kcal(template, foods_by_id)
        template_costs[t_id] = (cost, kcal, complete)
        if kcal > Decimal("0") and complete:
            rate = cost / kcal
            cat = str(template.category)
            if cat not in category_cheapest_rate or rate < category_cheapest_rate[cat]:
                category_cheapest_rate[cat] = rate

    min_weekly_cost = Decimal("0")

    for day in adapted_week.days:
        for slot in day.slots:
            is_snack = slot.category is MealCategory.SNACK
            target_kcal = snack_target_kcal if is_snack else main_target_kcal

            template_key = str(slot.meal_id) if slot.meal_id else None
            slot_cost = Decimal("0")
            slot_complete = False

            if template_key and template_key in template_costs:
                cost, kcal, slot_complete = template_costs[template_key]
                if not slot_complete:
                    price_coverage_complete = False
                if kcal > Decimal("0"):
                    slot_cost = target_kcal * (cost / kcal)
                else:
                    slot_cost = cost
            else:
                price_coverage_complete = False

            weekly_cost += slot_cost

            cat_str = str(slot.category.value if hasattr(slot.category, "value") else slot.category)
            if cat_str in category_cheapest_rate and target_kcal > Decimal("0"):
                min_weekly_cost += target_kcal * category_cheapest_rate[cat_str]
            else:
                min_weekly_cost += slot_cost

    monthly_cost = (weekly_cost * Decimal("52") / Decimal("12")).quantize(Decimal("1"))
    min_monthly_cost = (min_weekly_cost * Decimal("52") / Decimal("12")).quantize(Decimal("1"))

    effective_tier = resolve_budget_tier(monthly_cost).value
    reason_codes: list[str] = []

    if not price_coverage_complete:
        confidence = "uncertain"
        reason_codes.append("PROGRAM_COST_PREFLIGHT_UNCERTAIN")
    else:
        confidence = "high"

    if user_monthly_budget_irr is not None:
        user_budget_dec = Decimal(user_monthly_budget_irr)
        if monthly_cost <= user_budget_dec:
            reason_codes.append("PROGRAM_COST_WITHIN_USER_BUDGET")
        else:
            reason_codes.append("PROGRAM_COST_ABOVE_USER_BUDGET")

        user_tier = resolve_budget_tier(user_monthly_budget_irr).value
        if user_tier == effective_tier:
            reason_codes.append("BUDGET_TIER_MATCH")
        elif (user_tier == "economy" and effective_tier == "normal") or (
            user_tier == "normal" and effective_tier == "varied"
        ):
            reason_codes.append("BUDGET_TIER_ONE_LEVEL_HIGHER")
        elif user_tier == "economy" and effective_tier == "varied":
            reason_codes.append("BUDGET_TIER_TWO_LEVELS_HIGHER")

        if min_monthly_cost > user_budget_dec and price_coverage_complete:
            reason_codes.append("PROGRAM_BUDGET_PROVABLY_INFEASIBLE")

    minimum_adapted = min_monthly_cost if price_coverage_complete else None

    return ProgramCostEstimate(
        program_code=program.code,
        estimated_monthly_cost_irr=monthly_cost,
        minimum_adapted_monthly_cost_irr=minimum_adapted,
        effective_budget_tier=effective_tier,
        price_coverage_complete=price_coverage_complete,
        estimate_confidence=confidence,
        reason_codes=tuple(reason_codes),
    )
