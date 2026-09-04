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
