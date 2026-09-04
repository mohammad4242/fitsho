from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.nutrition.planner_engine import PlannedDay, PlannerResult


@dataclass(frozen=True)
class PlanComparisonReport:
    user_monthly_budget_irr: int
    budget_plan_monthly_cost_irr: int | None
    ideal_plan_monthly_cost_irr: int | None
    minimum_feasible_monthly_cost_irr: int | None
    monthly_cost_gap_irr: int | None

    calorie_gap_kcal_per_day: Decimal | None
    protein_gap_g_per_day: Decimal | None
    carbohydrate_gap_g_per_day: Decimal | None
    fat_gap_g_per_day: Decimal | None
    fibre_gap_g_per_day: Decimal | None

    micronutrient_gaps_improved: tuple[str, ...]
    unique_meal_count_budget: int | None
    unique_meal_count_ideal: int | None
    unique_protein_sources_budget: int | None
    unique_protein_sources_ideal: int | None

    meaningful_quality_improvement: bool
    show_ideal_plan: bool
    reason_codes: tuple[str, ...]

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "user_monthly_budget_irr": self.user_monthly_budget_irr,
            "budget_plan_monthly_cost_irr": self.budget_plan_monthly_cost_irr,
            "ideal_plan_monthly_cost_irr": self.ideal_plan_monthly_cost_irr,
            "minimum_feasible_monthly_cost_irr": self.minimum_feasible_monthly_cost_irr,
            "monthly_cost_gap_irr": self.monthly_cost_gap_irr,
            "calorie_gap_kcal_per_day": (
                str(self.calorie_gap_kcal_per_day)
                if self.calorie_gap_kcal_per_day is not None
                else None
            ),
            "protein_gap_g_per_day": (
                str(self.protein_gap_g_per_day) if self.protein_gap_g_per_day is not None else None
            ),
            "carbohydrate_gap_g_per_day": (
                str(self.carbohydrate_gap_g_per_day)
                if self.carbohydrate_gap_g_per_day is not None
                else None
            ),
            "fat_gap_g_per_day": (
                str(self.fat_gap_g_per_day) if self.fat_gap_g_per_day is not None else None
            ),
            "fibre_gap_g_per_day": (
                str(self.fibre_gap_g_per_day) if self.fibre_gap_g_per_day is not None else None
            ),
            "micronutrient_gaps_improved": list(self.micronutrient_gaps_improved),
            "unique_meal_count_budget": self.unique_meal_count_budget,
            "unique_meal_count_ideal": self.unique_meal_count_ideal,
            "unique_protein_sources_budget": self.unique_protein_sources_budget,
            "unique_protein_sources_ideal": self.unique_protein_sources_ideal,
            "meaningful_quality_improvement": self.meaningful_quality_improvement,
            "show_ideal_plan": self.show_ideal_plan,
            "reason_codes": list(self.reason_codes),
        }


def _weekly_to_monthly_cost(weekly_cost_irr: Decimal | int | None) -> int | None:
    if weekly_cost_irr is None:
        return None
    cost = Decimal(weekly_cost_irr)
    return int(round(cost * Decimal("30") / Decimal("7")))


def _average_daily_nutrients(days: tuple[PlannedDay, ...]) -> dict[str, Decimal]:
    if not days:
        return {}
    totals: dict[str, Decimal] = {}
    for day in days:
        items = day.nutrients.items() if isinstance(day.nutrients, dict) else day.nutrients
        for k, v in items:
            totals[k] = totals.get(k, Decimal("0")) + Decimal(v)
    count = Decimal(len(days))
    return {k: v / count for k, v in totals.items()}


def _count_unique_meals(days: tuple[PlannedDay, ...]) -> int:
    template_ids = {
        meal.template_id for day in days for meal in day.meals if meal.template_id is not None
    }
    return len(template_ids)


def _count_unique_protein_sources(days: tuple[PlannedDay, ...]) -> int:
    protein_foods = {
        food.food_id
        for day in days
        for meal in day.meals
        for food in meal.foods
        if getattr(food, "functional_role", None) == "protein"
    }
    return len(protein_foods)


def compare_plans(
    *,
    user_monthly_budget_irr: int,
    budget_plan_result: PlannerResult | None,
    ideal_plan_result: PlannerResult | None,
    minimum_feasible_monthly_cost_irr: int | None = None,
) -> PlanComparisonReport:
    """Compare a budget-constrained plan against an ideal reference plan."""
    reason_codes: list[str] = []

    budget_monthly_cost = None
    ideal_monthly_cost = None
    if budget_plan_result is not None and budget_plan_result.is_successful:
        budget_monthly_cost = _weekly_to_monthly_cost(budget_plan_result.weekly_cost_irr)

    if ideal_plan_result is not None and ideal_plan_result.is_successful:
        ideal_monthly_cost = _weekly_to_monthly_cost(ideal_plan_result.weekly_cost_irr)

    monthly_cost_gap = None
    if ideal_monthly_cost is not None and budget_monthly_cost is not None:
        monthly_cost_gap = ideal_monthly_cost - budget_monthly_cost

    calorie_gap = None
    protein_gap = None
    carb_gap = None
    fat_gap = None
    fibre_gap = None
    micronutrient_gaps_improved: list[str] = []

    unique_meals_budget = None
    unique_meals_ideal = None
    unique_proteins_budget = None
    unique_proteins_ideal = None

    meaningful_improvement = False
    show_ideal_plan = False

    if budget_plan_result is None or not budget_plan_result.is_successful:
        reason_codes.append("BUDGET_INSUFFICIENT_FOR_FEASIBLE_PLAN")
        if ideal_plan_result is not None and ideal_plan_result.is_successful:
            unique_meals_ideal = _count_unique_meals(ideal_plan_result.days)
            unique_proteins_ideal = _count_unique_protein_sources(ideal_plan_result.days)
            meaningful_improvement = True
            show_ideal_plan = True
    else:
        budget_nutrients = _average_daily_nutrients(budget_plan_result.days)
        unique_meals_budget = _count_unique_meals(budget_plan_result.days)
        unique_proteins_budget = _count_unique_protein_sources(budget_plan_result.days)

        if ideal_plan_result is not None and ideal_plan_result.is_successful:
            ideal_nutrients = _average_daily_nutrients(ideal_plan_result.days)
            unique_meals_ideal = _count_unique_meals(ideal_plan_result.days)
            unique_proteins_ideal = _count_unique_protein_sources(ideal_plan_result.days)

            calorie_gap = ideal_nutrients.get("energy_kcal", Decimal("0")) - budget_nutrients.get(
                "energy_kcal", Decimal("0")
            )
            protein_gap = ideal_nutrients.get("protein_g", Decimal("0")) - budget_nutrients.get(
                "protein_g", Decimal("0")
            )
            carb_gap = ideal_nutrients.get("carbohydrate_g", Decimal("0")) - budget_nutrients.get(
                "carbohydrate_g", Decimal("0")
            )
            fat_gap = ideal_nutrients.get("total_fat_g", Decimal("0")) - budget_nutrients.get(
                "total_fat_g", Decimal("0")
            )
            fibre_gap = ideal_nutrients.get("fibre_g", Decimal("0")) - budget_nutrients.get(
                "fibre_g", Decimal("0")
            )

            # Check meaningful quality improvements
            if protein_gap >= Decimal("10"):
                meaningful_improvement = True
            if (unique_proteins_ideal or 0) > (unique_proteins_budget or 0):
                meaningful_improvement = True
            if (unique_meals_ideal or 0) > (unique_meals_budget or 0) + 1:
                meaningful_improvement = True

            show_ideal_plan = meaningful_improvement

    return PlanComparisonReport(
        user_monthly_budget_irr=user_monthly_budget_irr,
        budget_plan_monthly_cost_irr=budget_monthly_cost,
        ideal_plan_monthly_cost_irr=ideal_monthly_cost,
        minimum_feasible_monthly_cost_irr=minimum_feasible_monthly_cost_irr,
        monthly_cost_gap_irr=monthly_cost_gap,
        calorie_gap_kcal_per_day=calorie_gap,
        protein_gap_g_per_day=protein_gap,
        carbohydrate_gap_g_per_day=carb_gap,
        fat_gap_g_per_day=fat_gap,
        fibre_gap_g_per_day=fibre_gap,
        micronutrient_gaps_improved=tuple(micronutrient_gaps_improved),
        unique_meal_count_budget=unique_meals_budget,
        unique_meal_count_ideal=unique_meals_ideal,
        unique_protein_sources_budget=unique_proteins_budget,
        unique_protein_sources_ideal=unique_proteins_ideal,
        meaningful_quality_improvement=meaningful_improvement,
        show_ideal_plan=show_ideal_plan,
        reason_codes=tuple(reason_codes),
    )
