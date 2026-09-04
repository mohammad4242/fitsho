from decimal import Decimal
from uuid import uuid4

from app.nutrition.enums import NutritionBudgetTier
from app.nutrition.planner_policy import (
    ECONOMY_MONTHLY_MAX_IRR,
    NORMAL_MONTHLY_MAX_IRR,
    resolve_budget_tier,
)
from app.nutrition.program_costing import (
    ProgramCostEstimate,
    estimate_program_cost,
)


def test_budget_tier_boundaries() -> None:
    assert resolve_budget_tier(Decimal("130000000")) == NutritionBudgetTier.ECONOMY
    assert resolve_budget_tier(Decimal("100000000")) == NutritionBudgetTier.ECONOMY
    assert resolve_budget_tier(Decimal("130000001")) == NutritionBudgetTier.NORMAL
    assert resolve_budget_tier(Decimal("180000000")) == NutritionBudgetTier.NORMAL
    assert resolve_budget_tier(Decimal("180000001")) == NutritionBudgetTier.VARIED
    assert resolve_budget_tier(Decimal("250000000")) == NutritionBudgetTier.VARIED


def test_toman_to_irr_conversion_constants() -> None:
    assert ECONOMY_MONTHLY_MAX_IRR == 130_000_000
    assert NORMAL_MONTHLY_MAX_IRR == 180_000_000


def test_program_cost_estimate_dataclass() -> None:
    estimate = ProgramCostEstimate(
        program_code="IRN01",
        estimated_monthly_cost_irr=Decimal("120000000"),
        minimum_adapted_monthly_cost_irr=Decimal("95000000"),
        effective_budget_tier=NutritionBudgetTier.ECONOMY.value,
        price_coverage_complete=True,
        estimate_confidence="high",
        reason_codes=("BUDGET_TIER_MATCH",),
    )
    assert estimate.program_code == "IRN01"
    assert estimate.effective_budget_tier == "economy"
    assert estimate.price_coverage_complete is True


def test_missing_price_yields_uncertain_estimate_without_false_rejection() -> None:
    estimate = ProgramCostEstimate(
        program_code="PREM01",
        estimated_monthly_cost_irr=Decimal("200000000"),
        minimum_adapted_monthly_cost_irr=None,
        effective_budget_tier=NutritionBudgetTier.VARIED.value,
        price_coverage_complete=False,
        estimate_confidence="uncertain",
        reason_codes=("PROGRAM_COST_PREFLIGHT_UNCERTAIN",),
    )
    assert estimate.price_coverage_complete is False
    assert estimate.estimate_confidence == "uncertain"
    assert "PROGRAM_COST_PREFLIGHT_UNCERTAIN" in estimate.reason_codes


def test_estimate_program_cost_deterministic_and_substitutes() -> None:
    from app.nutrition.enums import MealCategory, NutritionDietStyle
    from app.nutrition.models import (
        NutritionCatalogueMeal,
        NutritionProgram,
        NutritionProgramDay,
        NutritionProgramSlot,
    )
    from app.nutrition.planner_engine import (
        PlannerFood,
        PlannerMealIngredient,
        PlannerMealTemplate,
    )

    meal_id1 = uuid4()
    meal_id2 = uuid4()

    food1 = PlannerFood(
        food_id="food-1",
        slug="rice",
        name_fa="برنج",
        name_en="Rice",
        roles=("main_staple",),
        nutrients_per_100g={"energy_kcal": Decimal("360")},
        price_irr_per_gram=Decimal("100"),
        price_reference_id="pr-1",
    )
    food2 = PlannerFood(
        food_id="food-2",
        slug="chicken",
        name_fa="مرغ",
        name_en="Chicken",
        roles=("main_protein",),
        nutrients_per_100g={"energy_kcal": Decimal("165")},
        price_irr_per_gram=Decimal("250"),
        price_reference_id="pr-2",
    )
    foods_by_id = {"food-1": food1, "food-2": food2}

    tpl1 = PlannerMealTemplate(
        meal_id=str(meal_id1),
        name_fa="مرغ با برنج",
        name_en="Chicken Rice",
        category="lunch",
        items=(
            PlannerMealIngredient(
                food_id="food-1",
                reference_grams=Decimal("100"),
                min_grams=Decimal("50"),
                max_grams=Decimal("200"),
                is_required=True,
                functional_role="staple",
            ),
            PlannerMealIngredient(
                food_id="food-2",
                reference_grams=Decimal("150"),
                min_grams=Decimal("50"),
                max_grams=Decimal("250"),
                is_required=True,
                functional_role="protein",
            ),
        ),
    )
    tpl_cheap = PlannerMealTemplate(
        meal_id=str(meal_id2),
        name_fa="برنج ساده",
        name_en="Plain Rice",
        category="lunch",
        items=(
            PlannerMealIngredient(
                food_id="food-1",
                reference_grams=Decimal("150"),
                min_grams=Decimal("50"),
                max_grams=Decimal("200"),
                is_required=True,
                functional_role="staple",
            ),
        ),
    )

    templates_by_id = {str(meal_id1): tpl1, str(meal_id2): tpl_cheap}

    program = NutritionProgram(
        code="TEST01",
        slug="test01",
        diet_style=NutritionDietStyle.BALANCED_IRANIAN,
        days=[
            NutritionProgramDay(
                day_number=i,
                slots=[
                    NutritionProgramSlot(
                        category=MealCategory.BREAKFAST,
                        meal_id=meal_id1,
                        meal=NutritionCatalogueMeal(
                            id=meal_id1,
                            code="M1",
                            category=MealCategory.BREAKFAST,
                            name_fa="صبحانه",
                            name_en="Breakfast",
                        ),
                    ),
                    NutritionProgramSlot(
                        category=MealCategory.LUNCH,
                        meal_id=meal_id1,
                        meal=NutritionCatalogueMeal(
                            id=meal_id1,
                            code="M1",
                            category=MealCategory.LUNCH,
                            name_fa="ناهار",
                            name_en="Lunch",
                        ),
                    ),
                    NutritionProgramSlot(
                        category=MealCategory.SNACK,
                        meal_id=meal_id1,
                        meal=NutritionCatalogueMeal(
                            id=meal_id1,
                            code="M1",
                            category=MealCategory.SNACK,
                            name_fa="میان‌وعده",
                            name_en="Snack",
                        ),
                    ),
                    NutritionProgramSlot(
                        category=MealCategory.DINNER,
                        meal_id=meal_id1,
                        meal=NutritionCatalogueMeal(
                            id=meal_id1,
                            code="M1",
                            category=MealCategory.DINNER,
                            name_fa="شام",
                            name_en="Dinner",
                        ),
                    ),
                ],
            )
            for i in range(1, 8)
        ],
    )

    estimate1 = estimate_program_cost(
        program,
        main_meal_slots=3,
        snack_slots=0,
        daily_kcal=Decimal("2000"),
        meal_templates_by_id=templates_by_id,
        foods_by_id=foods_by_id,
        user_monthly_budget_irr=100_000_000,
    )
    estimate2 = estimate_program_cost(
        program,
        main_meal_slots=3,
        snack_slots=0,
        daily_kcal=Decimal("2000"),
        meal_templates_by_id=templates_by_id,
        foods_by_id=foods_by_id,
        user_monthly_budget_irr=100_000_000,
    )

    assert estimate1.estimated_monthly_cost_irr == estimate2.estimated_monthly_cost_irr
    assert estimate1.price_coverage_complete is True
    assert estimate1.estimate_confidence == "high"
    assert estimate1.minimum_adapted_monthly_cost_irr is not None
    assert estimate1.minimum_adapted_monthly_cost_irr <= estimate1.estimated_monthly_cost_irr
