from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.nutrition.planner_engine import PlannedDay, PlannerResult

PLAN_COMPARISON_POLICY_VERSION = "nutrition-plan-comparison-v1"
MIN_IDEAL_DISPLAY_COST_GAP_IRR = 10_000_000
MIN_PROTEIN_IMPROVEMENT_G = Decimal("10")
MIN_CORE_DEVIATION_IMPROVEMENT = Decimal("0.05")
MIN_UNIQUE_MEAL_IMPROVEMENT = 3
MIN_PROTEIN_SOURCE_IMPROVEMENT = 2
MIN_GOAL_QUALITY_IMPROVEMENT = Decimal("0.05")


@dataclass(frozen=True)
class PlanComparisonMetric:
    budget_value: float | int | None
    ideal_value: float | int | None
    difference: float | int | None
    unit: str
    target_value: float | int | None = None

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "budget_value": self.budget_value,
            "ideal_value": self.ideal_value,
            "difference": self.difference,
            "unit": self.unit,
            "target_value": self.target_value,
        }


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

    calorie_gap: PlanComparisonMetric | None
    protein_gap: PlanComparisonMetric | None
    carbohydrate_gap: PlanComparisonMetric | None
    fat_gap: PlanComparisonMetric | None
    fibre_gap: PlanComparisonMetric | None

    micronutrient_gaps_improved: tuple[str, ...]
    unique_meal_count_budget: int | None
    unique_meal_count_ideal: int | None
    unique_protein_sources_budget: int | None
    unique_protein_sources_ideal: int | None

    meaningful_quality_improvement: bool
    show_ideal_plan: bool
    reason_codes: tuple[str, ...]
    policy_version: str = PLAN_COMPARISON_POLICY_VERSION

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
            "calorie_gap": self.calorie_gap.to_snapshot() if self.calorie_gap else None,
            "protein_gap": self.protein_gap.to_snapshot() if self.protein_gap else None,
            "carbohydrate_gap": (
                self.carbohydrate_gap.to_snapshot() if self.carbohydrate_gap else None
            ),
            "fat_gap": self.fat_gap.to_snapshot() if self.fat_gap else None,
            "fibre_gap": self.fibre_gap.to_snapshot() if self.fibre_gap else None,
            "micronutrient_gaps_improved": list(self.micronutrient_gaps_improved),
            "unique_meal_count_budget": self.unique_meal_count_budget,
            "unique_meal_count_ideal": self.unique_meal_count_ideal,
            "unique_protein_sources_budget": self.unique_protein_sources_budget,
            "unique_protein_sources_ideal": self.unique_protein_sources_ideal,
            "meaningful_quality_improvement": self.meaningful_quality_improvement,
            "show_ideal_plan": self.show_ideal_plan,
            "reason_codes": list(self.reason_codes),
            "policy_version": self.policy_version,
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

    budget_nutrients: dict[str, Decimal] = {}
    ideal_nutrients: dict[str, Decimal] = {}
    b_comps = budget_plan_result.nutrient_comparisons or {} if budget_plan_result else {}
    i_comps = ideal_plan_result.nutrient_comparisons or {} if ideal_plan_result else {}

    if budget_plan_result is None or not budget_plan_result.is_successful:
        reason_codes.append("NO_BUDGET_FEASIBLE_PLAN_FOUND")
        reason_codes.append("BUDGET_INSUFFICIENT_FOR_FEASIBLE_PLAN")
        if (
            minimum_feasible_monthly_cost_irr is not None
            and user_monthly_budget_irr < minimum_feasible_monthly_cost_irr
        ):
            reason_codes.append("USER_BUDGET_BELOW_MINIMUM_FEASIBLE")

        if ideal_plan_result is not None and ideal_plan_result.is_successful:
            ideal_nutrients = _average_daily_nutrients(ideal_plan_result.days)
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

            # Rule A: preferred protein gap improves by >= 10 g/day
            if protein_gap >= MIN_PROTEIN_IMPROVEMENT_G:
                meaningful_improvement = True

            # Rule B: core target max deviation improves by >= 0.05
            core_keys = ("goal_calories", "protein", "carbohydrate", "total_fat")
            b_comps = budget_plan_result.nutrient_comparisons or {}
            i_comps = ideal_plan_result.nutrient_comparisons or {}
            b_devs: list[Decimal] = []
            for k in core_keys:
                if k in b_comps:
                    pref = b_comps[k].preferred
                    if pref is not None and pref > Decimal("0"):
                        b_devs.append(abs(b_comps[k].planned - pref) / pref)
            i_devs: list[Decimal] = []
            for k in core_keys:
                if k in i_comps:
                    pref = i_comps[k].preferred
                    if pref is not None and pref > Decimal("0"):
                        i_devs.append(abs(i_comps[k].planned - pref) / pref)
            if b_devs and i_devs:
                max_b = max(b_devs)
                max_i = max(i_devs)
                if (max_b - max_i) >= MIN_CORE_DEVIATION_IMPROVEMENT:
                    meaningful_improvement = True

            # Rule C: at least 2 micronutrient preferred gaps resolved in Ideal
            for nutrient_code, b_comp in b_comps.items():
                if nutrient_code in core_keys:
                    continue
                if b_comp.status in ("below_reference_target", "below_preferred_but_acceptable"):
                    i_comp = i_comps.get(nutrient_code)
                    if i_comp and i_comp.status == "within_target":
                        micronutrient_gaps_improved.append(nutrient_code)

            if len(micronutrient_gaps_improved) >= 2:
                meaningful_improvement = True

            # Rule D: unique meal templates improve by >= 3
            meal_diff = (unique_meals_ideal or 0) - (unique_meals_budget or 0)
            if meal_diff >= MIN_UNIQUE_MEAL_IMPROVEMENT:
                meaningful_improvement = True

            # Rule E: unique protein-source foods improve by >= 2
            protein_diff = (unique_proteins_ideal or 0) - (unique_proteins_budget or 0)
            if protein_diff >= MIN_PROTEIN_SOURCE_IMPROVEMENT:
                meaningful_improvement = True

            # Threshold and display decision
            show_ideal_plan = (
                monthly_cost_gap is not None
                and monthly_cost_gap >= MIN_IDEAL_DISPLAY_COST_GAP_IRR
                and meaningful_improvement
            )

            if monthly_cost_gap is not None and monthly_cost_gap < MIN_IDEAL_DISPLAY_COST_GAP_IRR:
                reason_codes.append("IDEAL_PLAN_HIDDEN_COST_GAP_SMALL")
            elif not meaningful_improvement:
                reason_codes.append("IDEAL_PLAN_HIDDEN_NO_MEANINGFUL_GAIN")
            else:
                reason_codes.append("IDEAL_PLAN_SHOWN_MEANINGFUL_GAIN")

            if protein_gap >= MIN_PROTEIN_IMPROVEMENT_G:
                reason_codes.append("BUDGET_PLAN_PROTEIN_PREFERRED_GAP")
            if calorie_gap is not None and calorie_gap >= Decimal("100"):
                reason_codes.append("BUDGET_PLAN_CALORIE_PREFERRED_GAP")
            if meal_diff >= 2 or protein_diff >= 1:
                reason_codes.append("BUDGET_PLAN_VARIETY_GAP")
            if len(micronutrient_gaps_improved) >= 1:
                reason_codes.append("BUDGET_PLAN_MICRONUTRIENT_GAP")

    def _make_metric(
        b_key: str,
        gap_val: Decimal | None,
        unit: str,
        comp_key: str | None = None,
    ) -> PlanComparisonMetric | None:
        if gap_val is None and not budget_nutrients and not ideal_nutrients:
            return None
        b_val = round(float(budget_nutrients.get(b_key, 0)), 1) if budget_nutrients else None
        i_val = round(float(ideal_nutrients.get(b_key, 0)), 1) if ideal_nutrients else None
        d_val = round(float(gap_val), 1) if gap_val is not None else None
        t_val: float | int | None = None
        if comp_key:
            target = None
            if comp_key in b_comps and b_comps[comp_key].preferred is not None:
                target = b_comps[comp_key].preferred
            elif comp_key in i_comps and i_comps[comp_key].preferred is not None:
                target = i_comps[comp_key].preferred
            if target is not None:
                t_val = round(float(target), 1)
        return PlanComparisonMetric(
            budget_value=b_val,
            ideal_value=i_val,
            difference=d_val,
            unit=unit,
            target_value=t_val,
        )

    metric_calorie = _make_metric("energy_kcal", calorie_gap, "kcal/day", "goal_calories")
    metric_protein = _make_metric("protein_g", protein_gap, "g/day", "protein")
    metric_carb = _make_metric("carbohydrate_g", carb_gap, "g/day", "carbohydrate")
    metric_fat = _make_metric("total_fat_g", fat_gap, "g/day", "total_fat")
    metric_fibre = _make_metric("fibre_g", fibre_gap, "g/day", "fibre")

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
        calorie_gap=metric_calorie,
        protein_gap=metric_protein,
        carbohydrate_gap=metric_carb,
        fat_gap=metric_fat,
        fibre_gap=metric_fibre,
        micronutrient_gaps_improved=tuple(sorted(set(micronutrient_gaps_improved))),
        unique_meal_count_budget=unique_meals_budget,
        unique_meal_count_ideal=unique_meals_ideal,
        unique_protein_sources_budget=unique_proteins_budget,
        unique_protein_sources_ideal=unique_proteins_ideal,
        meaningful_quality_improvement=meaningful_improvement,
        show_ideal_plan=show_ideal_plan,
        reason_codes=tuple(reason_codes),
        policy_version=PLAN_COMPARISON_POLICY_VERSION,
    )
