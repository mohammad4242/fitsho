from decimal import Decimal
from uuid import uuid4

from app.nutrition.enums import NutritionDietStyle
from app.nutrition.models import NutritionProgram
from app.nutrition.nutrition_request import NormalizedNutritionRequest
from app.nutrition.program_scoring import (
    score_program,
)


def _request(
    *,
    goal: str = "build_muscle",
    trains: bool = True,
    exercise_type: str = "resistance",
) -> NormalizedNutritionRequest:
    return NormalizedNutritionRequest(
        user_id=str(uuid4()),
        fitness_goal=goal,
        body_weight_kg=Decimal("75.0"),
        protein_calculation_weight_kg=Decimal("75.0"),
        tdee_kcal=Decimal("2200.0"),
        monthly_budget_irr=120_000_000,
        weekly_budget_irr=27_692_307,
        budget_style="flexible",
        trains=trains,
        exercise_type=exercise_type,
        training_days_per_week=4,
        training_minutes_per_session=60,
        training_intensity="moderate",
        training_experience="intermediate",
        main_meal_slots=3,
        snack_slots=1,
        dietary_pattern="omnivore",
        maximum_meal_repetition_per_week=2,
        preferred_variety="medium",
        requested_weight_change_kg_per_week=None,
    )


def test_score_program_prefers_matching_diet_style() -> None:
    req = _request(goal="build_muscle", trains=True, exercise_type="resistance")
    gym_program = NutritionProgram(
        code="GYM01",
        slug="gym01",
        diet_style=NutritionDietStyle.HIGH_PROTEIN_GYM,
    )
    irn_program = NutritionProgram(
        code="IRN01",
        slug="irn01",
        diet_style=NutritionDietStyle.BALANCED_IRANIAN,
    )

    gym_score = score_program(gym_program, req)
    irn_score = score_program(irn_program, req)

    assert gym_score.score.total > irn_score.score.total
    assert "PREFERRED_DIET_STYLE" in gym_score.reason_codes
    assert "PREFERRED_DIET_STYLE" not in irn_score.reason_codes


def test_score_program_budget_tier_penalties() -> None:
    from app.nutrition.enums import NutritionBudgetTier
    from app.nutrition.program_costing import ProgramCostEstimate

    # User with economy budget (100M IRR)
    req = _request()
    req = NormalizedNutritionRequest(
        **{**req.__dict__, "monthly_budget_irr": 100_000_000, "budget_style": "strict"}
    )

    eco_prog = NutritionProgram(
        code="ECO01",
        slug="eco01",
        diet_style=NutritionDietStyle.ECONOMY,
        budget_tier_hint=NutritionBudgetTier.ECONOMY,
    )
    norm_prog = NutritionProgram(
        code="IRN01",
        slug="irn01",
        diet_style=NutritionDietStyle.BALANCED_IRANIAN,
        budget_tier_hint=NutritionBudgetTier.NORMAL,
    )
    prem_prog = NutritionProgram(
        code="PREM01",
        slug="prem01",
        diet_style=NutritionDietStyle.PREMIUM_VARIED,
        budget_tier_hint=NutritionBudgetTier.VARIED,
    )

    eco_est = ProgramCostEstimate(
        program_code="ECO01",
        estimated_monthly_cost_irr=Decimal("95000000"),
        minimum_adapted_monthly_cost_irr=Decimal("85000000"),
        effective_budget_tier="economy",
        price_coverage_complete=True,
        estimate_confidence="high",
        reason_codes=(),
    )
    norm_est = ProgramCostEstimate(
        program_code="IRN01",
        estimated_monthly_cost_irr=Decimal("140000000"),
        minimum_adapted_monthly_cost_irr=Decimal("98000000"),
        effective_budget_tier="normal",
        price_coverage_complete=True,
        estimate_confidence="high",
        reason_codes=(),
    )
    prem_est = ProgramCostEstimate(
        program_code="PREM01",
        estimated_monthly_cost_irr=Decimal("200000000"),
        minimum_adapted_monthly_cost_irr=Decimal("100000000"),
        effective_budget_tier="varied",
        price_coverage_complete=True,
        estimate_confidence="high",
        reason_codes=(),
    )

    eco_res = score_program(eco_prog, req, cost_estimate=eco_est)
    norm_res = score_program(norm_prog, req, cost_estimate=norm_est)
    prem_res = score_program(prem_prog, req, cost_estimate=prem_est)

    assert "BUDGET_TIER_MATCH" in eco_res.reason_codes
    assert "PROGRAM_COST_WITHIN_USER_BUDGET" in eco_res.reason_codes

    assert "BUDGET_TIER_ONE_LEVEL_HIGHER" in norm_res.reason_codes
    assert "PROGRAM_COST_ABOVE_USER_BUDGET" in norm_res.reason_codes

    assert "BUDGET_TIER_TWO_LEVELS_HIGHER" in prem_res.reason_codes
    assert "PROGRAM_COST_ABOVE_USER_BUDGET" in prem_res.reason_codes

    assert eco_res.score.budget_score > norm_res.score.budget_score
    assert norm_res.score.budget_score > prem_res.score.budget_score
    # In budget mode, economy program significantly beats premium program
    assert eco_res.score.total > prem_res.score.total
