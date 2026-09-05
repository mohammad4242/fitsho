from decimal import Decimal
from uuid import uuid4

from app.nutrition.nutrition_request import (
    NormalizedNutritionRequest,
)


def test_normalized_nutrition_request_initialization() -> None:
    user_id = str(uuid4())
    req = NormalizedNutritionRequest(
        user_id=user_id,
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

    assert req.user_id == user_id
    assert req.fitness_goal == "lose_weight"
    assert req.body_weight_kg == Decimal("75.0")
    assert req.requested_weight_change_kg_per_week is None
    assert req.weight_rate_mode == "safe"
    assert req.trains is True
