from decimal import Decimal
from uuid import uuid4

from app.nutrition.enums import NutritionDietStyle
from app.nutrition.models import NutritionProgram
from app.nutrition.nutrition_request import NormalizedNutritionRequest
from app.nutrition.program_eligibility import (
    check_program_eligibility,
)


def _request() -> NormalizedNutritionRequest:
    return NormalizedNutritionRequest(
        user_id=str(uuid4()),
        fitness_goal="lose_weight",
        body_weight_kg=Decimal("75.0"),
        protein_calculation_weight_kg=Decimal("75.0"),
        tdee_kcal=Decimal("2200.0"),
        monthly_budget_irr=120_000_000,
        weekly_budget_irr=27_692_307,
        budget_style="strict",
        trains=True,
        exercise_type="resistance",
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


def test_active_program_is_eligible() -> None:
    program = NutritionProgram(
        code="IRN01",
        slug="irn01",
        diet_style=NutritionDietStyle.BALANCED_IRANIAN,
        is_active=True,
    )
    result = check_program_eligibility(program, _request())
    assert result.eligible is True
    assert result.reason_codes == ()


def test_inactive_program_is_rejected() -> None:
    program = NutritionProgram(
        code="IRN01",
        slug="irn01",
        diet_style=NutritionDietStyle.BALANCED_IRANIAN,
        is_active=False,
    )
    result = check_program_eligibility(program, _request())
    assert result.eligible is False
    assert "PROGRAM_INACTIVE" in result.reason_codes


def test_program_with_minimum_adapted_cost_above_budget_is_hard_rejected() -> None:
    from app.nutrition.program_costing import ProgramCostEstimate

    program = NutritionProgram(
        code="PREM01",
        slug="prem01",
        diet_style=NutritionDietStyle.PREMIUM_VARIED,
        is_active=True,
    )
    # Request monthly budget: 120_000_000 IRR
    req = _request()
    cost_estimate = ProgramCostEstimate(
        program_code="PREM01",
        estimated_monthly_cost_irr=Decimal("190000000"),
        minimum_adapted_monthly_cost_irr=Decimal("160000000"),  # > 120M
        effective_budget_tier="varied",
        price_coverage_complete=True,
        estimate_confidence="high",
        reason_codes=(),
    )
    result = check_program_eligibility(program, req, cost_estimate=cost_estimate)
    assert result.eligible is False
    assert "PROGRAM_BUDGET_PROVABLY_INFEASIBLE" in result.reason_codes


def test_program_with_uncertain_cost_is_never_hard_rejected() -> None:
    from app.nutrition.program_costing import ProgramCostEstimate

    program = NutritionProgram(
        code="PREM01",
        slug="prem01",
        diet_style=NutritionDietStyle.PREMIUM_VARIED,
        is_active=True,
    )
    req = _request()
    cost_estimate = ProgramCostEstimate(
        program_code="PREM01",
        estimated_monthly_cost_irr=Decimal("190000000"),
        minimum_adapted_monthly_cost_irr=None,  # uncertain lower bound
        effective_budget_tier="varied",
        price_coverage_complete=False,
        estimate_confidence="uncertain",
        reason_codes=("PROGRAM_COST_PREFLIGHT_UNCERTAIN",),
    )
    result = check_program_eligibility(program, req, cost_estimate=cost_estimate)
    assert result.eligible is True
    assert "PROGRAM_BUDGET_PROVABLY_INFEASIBLE" not in result.reason_codes
