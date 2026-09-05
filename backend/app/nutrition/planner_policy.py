from dataclasses import dataclass
from decimal import Decimal

from app.nutrition.enums import NutritionBudgetTier

PLANNER_POLICY_VERSION = "weekly-planner-v1"
MEAL_DISTRIBUTION_POLICY_VERSION = "meal-distribution-v1"
PORTION_POLICY_VERSION = "bounded-portion-solver-v1"
PLANNER_VERSION = "nutrition-planner-portion-solver-v2"
CANDIDATE_SELECTION_POLICY_VERSION = "best-admitted-all-active-programs-quality-v2"
PREFERENCE_QUALITY_POLICY_VERSION = "preference-adherence-quality-v1"
TEMPLATE_SUBSTITUTION_POLICY_VERSION = "safe-template-substitution-beam-v1"
BUDGET_OPTIMIZER_POLICY_VERSION = "deterministic-budget-optimizer-v1"
PROGRAM_SELECTION_POLICY_VERSION = "nutrition-program-selection-v3"
PROGRAM_COSTING_POLICY_VERSION = "nutrition-program-costing-v1"
GOAL_STRATEGY_VERSION = "nutrition-goal-strategy-v1"
WEIGHT_RATE_POLICY_VERSION = "nutrition-weight-rate-v1"
MACRO_RESOLUTION_POLICY_VERSION = "nutrition-macro-resolution-v2"

ECONOMY_MONTHLY_MAX_IRR = 130_000_000
NORMAL_MONTHLY_MAX_IRR = 180_000_000
INITIAL_PROGRAM_BATCH_SIZE = 5
MAX_PROGRAM_FALLBACK_BATCHES = 1


def resolve_budget_tier(monthly_cost_irr: int | Decimal) -> NutritionBudgetTier:
    cost = Decimal(monthly_cost_irr)
    if cost <= Decimal(ECONOMY_MONTHLY_MAX_IRR):
        return NutritionBudgetTier.ECONOMY
    if cost <= Decimal(NORMAL_MONTHLY_MAX_IRR):
        return NutritionBudgetTier.NORMAL
    return NutritionBudgetTier.VARIED


@dataclass(frozen=True)
class PlannerPolicy:
    flexible_budget_overage_cap: Decimal = Decimal("0.15")
    snack_energy_share: Decimal = Decimal("0.15")
    protein_energy_share: Decimal = Decimal("0.35")
    minimum_portion_g: Decimal = Decimal("10")
    maximum_main_food_portion_g: Decimal = Decimal("450")
    maximum_snack_portion_g: Decimal = Decimal("500")
    maximum_repair_iterations: int = 3
    repair_portion_g: Decimal = Decimal("50")
    calorie_tolerance_ratio: Decimal = Decimal("0.20")
    macro_tolerance_ratio: Decimal = Decimal("0.10")
    micronutrient_data_completeness_threshold: Decimal = Decimal("0.80")
    maximum_price_age_hours: int = 168
    minimum_main_protein_candidates: int = 1
    minimum_main_staple_candidates: int = 1
    minimum_snack_candidates: int = 1
    micronutrient_score_weight: Decimal = Decimal("4")
    preference_score_weight: Decimal = Decimal("1")
    cost_score_weight: Decimal = Decimal("0.25")
    maximum_template_substitution_attempts_per_slot: int = 2
    maximum_candidate_rebuild_attempts: int = 2
    maximum_substitutes_per_slot: int = 2
    maximum_partial_variants_per_program: int = 8
    maximum_full_variants_per_program: int = 2
    maximum_budget_repair_iterations: int = 12
    maximum_budget_feasibility_variants: int = 24
    maximum_budget_alternatives_per_slot: int = 6
    portion_adjustment_increment_g: Decimal = Decimal("5")
    maximum_portion_solver_iterations: int = 40
    maximum_combined_repair_passes: int = 2


DEFAULT_POLICY = PlannerPolicy()
