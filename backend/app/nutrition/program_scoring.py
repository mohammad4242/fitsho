from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from app.nutrition.enums import (
    NutritionBudgetTier,
    NutritionDietStyle,
    NutritionOptimizationMode,
)
from app.nutrition.models import NutritionProgram
from app.nutrition.nutrition_request import NormalizedNutritionRequest
from app.nutrition.planner_policy import resolve_budget_tier

if TYPE_CHECKING:
    from app.nutrition.program_costing import ProgramCostEstimate


@dataclass(frozen=True)
class ProgramScore:
    budget_score: int
    goal_score: int
    training_score: int
    meal_structure_score: int
    preference_score: int
    total: int


@dataclass(frozen=True)
class ProgramScoringResult:
    score: ProgramScore
    reason_codes: tuple[str, ...]


def select_preferred_diet_style(request: NormalizedNutritionRequest) -> NutritionDietStyle:
    if (
        request.fitness_goal in {"build_muscle", "body_recomposition"}
        and request.trains
        and request.exercise_type in {"resistance", "mixed"}
    ):
        return NutritionDietStyle.HIGH_PROTEIN_GYM
    if request.plan_style == "economical":
        return NutritionDietStyle.ECONOMY
    if (
        request.plan_style == "simple"
        or request.cooking_skill == "none"
        or (
            request.maximum_cooking_time_minutes is not None
            and request.maximum_cooking_time_minutes <= 20
        )
        or request.meal_preparation_preference == "no_cooking"
    ):
        return NutritionDietStyle.QUICK_EASY
    if request.preferred_variety == "high" and request.budget_style == "flexible":
        return NutritionDietStyle.PREMIUM_VARIED
    return NutritionDietStyle.BALANCED_IRANIAN


_TIER_LEVELS = {
    NutritionBudgetTier.ECONOMY.value: 0,
    NutritionBudgetTier.NORMAL.value: 1,
    NutritionBudgetTier.VARIED.value: 2,
}


def score_program(
    program: NutritionProgram,
    request: NormalizedNutritionRequest,
    *,
    cost_estimate: "ProgramCostEstimate | None" = None,
    mode: NutritionOptimizationMode = NutritionOptimizationMode.BUDGET_CONSTRAINED,
) -> ProgramScoringResult:
    reason_codes: list[str] = []

    user_budget_irr = request.monthly_budget_irr if request.monthly_budget_irr else 150_000_000
    user_tier = resolve_budget_tier(user_budget_irr)
    user_level = _TIER_LEVELS.get(user_tier.value, 1)

    if cost_estimate is not None:
        prog_tier_str = cost_estimate.effective_budget_tier
        if not cost_estimate.price_coverage_complete:
            reason_codes.append("PROGRAM_COST_PREFLIGHT_UNCERTAIN")
    elif program.budget_tier_hint is not None:
        prog_tier_str = (
            program.budget_tier_hint.value
            if hasattr(program.budget_tier_hint, "value")
            else str(program.budget_tier_hint)
        )
    else:
        prog_tier_str = NutritionBudgetTier.NORMAL.value

    prog_level = _TIER_LEVELS.get(prog_tier_str, 1)
    delta_tier = prog_level - user_level

    user_monthly_budget = (
        Decimal(str(request.monthly_budget_irr)) if request.monthly_budget_irr is not None else None
    )

    if delta_tier <= 0:
        reason_codes.append("BUDGET_TIER_MATCH")
    elif delta_tier == 1:
        reason_codes.append("BUDGET_TIER_ONE_LEVEL_HIGHER")
    else:
        reason_codes.append("BUDGET_TIER_TWO_LEVELS_HIGHER")

    if cost_estimate is not None and user_monthly_budget is not None:
        if cost_estimate.estimated_monthly_cost_irr <= user_monthly_budget:
            reason_codes.append("PROGRAM_COST_WITHIN_USER_BUDGET")
            within_direct_budget = True
        else:
            reason_codes.append("PROGRAM_COST_ABOVE_USER_BUDGET")
            within_direct_budget = False
    else:
        within_direct_budget = delta_tier <= 0

    if (
        cost_estimate is not None
        and cost_estimate.minimum_adapted_monthly_cost_irr is not None
        and user_monthly_budget is not None
        and cost_estimate.minimum_adapted_monthly_cost_irr > user_monthly_budget
    ):
        reason_codes.append("PROGRAM_BUDGET_PROVABLY_INFEASIBLE")
        budget_score = 0
    else:
        if delta_tier <= 0:
            budget_score = 100 if within_direct_budget else 70
        elif delta_tier == 1:
            budget_score = 60 if within_direct_budget else 35
        else:
            budget_score = 30 if within_direct_budget else 10

    preferred_style = select_preferred_diet_style(request)
    is_preferred = program.diet_style is preferred_style
    preference_score = 100 if is_preferred else 0
    if is_preferred:
        reason_codes.append("PREFERRED_DIET_STYLE")

    # Goal alignment scoring (25%)
    goal = request.fitness_goal.lower()
    if goal in {"build_muscle", "body_recomposition"}:
        if program.diet_style == NutritionDietStyle.HIGH_PROTEIN_GYM:
            goal_score = 100
            reason_codes.append("GOAL_PROTEIN_ALIGNMENT")
        else:
            goal_score = 50
    elif goal == "fat_loss":
        if program.diet_style == NutritionDietStyle.HIGH_PROTEIN_GYM:
            goal_score = 95
            reason_codes.append("GOAL_PROTEIN_ALIGNMENT")
        elif program.diet_style == NutritionDietStyle.BALANCED_IRANIAN:
            goal_score = 85
        else:
            goal_score = 65
    elif goal in {"lose_weight", "gain_weight"}:
        if program.diet_style in {
            NutritionDietStyle.BALANCED_IRANIAN,
            NutritionDietStyle.ECONOMY,
            NutritionDietStyle.PREMIUM_VARIED,
        }:
            goal_score = 90
        else:
            goal_score = 75
    else:
        goal_score = 80

    # Training alignment scoring (10%)
    if request.trains and request.exercise_type in {"resistance", "mixed"}:
        if program.diet_style == NutritionDietStyle.HIGH_PROTEIN_GYM:
            training_score = 100
            reason_codes.append("TRAINING_STYLE_MATCH")
        else:
            training_score = 70
    else:
        training_score = 80

    # Meal structure scoring (10%)
    meal_structure_score = 100

    # Weighting:
    if mode == NutritionOptimizationMode.IDEAL_REFERENCE:
        # Ideal mode: budget weight is 0. Goal 45%, Preference 25%, Training 15%, Meal structure 15%
        goal_part = Decimal(str(goal_score)) * Decimal("0.45")
        pref_part = Decimal(str(preference_score)) * Decimal("0.25")
        train_part = Decimal(str(training_score)) * Decimal("0.15")
        meal_part = Decimal(str(meal_structure_score)) * Decimal("0.15")
        total = int(round(goal_part + pref_part + train_part + meal_part))
    else:
        # Budget mode: Budget 40%, Goal 25%, Preference 15%, Training 10%, Meal structure 10%
        budget_part = Decimal(str(budget_score)) * Decimal("0.40")
        goal_part = Decimal(str(goal_score)) * Decimal("0.25")
        pref_part = Decimal(str(preference_score)) * Decimal("0.15")
        train_part = Decimal(str(training_score)) * Decimal("0.10")
        meal_part = Decimal(str(meal_structure_score)) * Decimal("0.10")
        total = int(round(budget_part + goal_part + pref_part + train_part + meal_part))

    return ProgramScoringResult(
        score=ProgramScore(
            budget_score=budget_score,
            goal_score=goal_score,
            training_score=training_score,
            meal_structure_score=meal_structure_score,
            preference_score=preference_score,
            total=total,
        ),
        reason_codes=tuple(dict.fromkeys(reason_codes)),
    )
