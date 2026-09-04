from decimal import Decimal

from app.nutrition.plan_comparison import (
    compare_plans,
)
from app.nutrition.planner_engine import (
    GenerationOutcome,
    PlannedDay,
    PlannedFood,
    PlannedMeal,
    PlannerResult,
)


def _make_dummy_plan(
    outcome: GenerationOutcome = GenerationOutcome.SUCCESS,
    weekly_cost_irr: int = 700_000,
    daily_calories: Decimal = Decimal("2000"),
    daily_protein: Decimal = Decimal("140"),
    daily_carb: Decimal = Decimal("200"),
    daily_fat: Decimal = Decimal("60"),
    daily_fibre: Decimal = Decimal("25"),
    food_slugs: tuple[str, ...] = ("chicken-breast", "rice"),
    protein_slugs: tuple[str, ...] = ("chicken-breast",),
) -> PlannerResult:
    foods = tuple(
        PlannedFood(
            food_id=f"food-{slug}",
            slug=slug,
            name_fa=slug,
            name_en=slug,
            roles=("main",),
            grams=Decimal("100"),
            cost_irr=Decimal(weekly_cost_irr) / Decimal("14"),
            nutrients=(
                ("energy_kcal", daily_calories / Decimal("2")),
                ("protein_g", daily_protein / Decimal("2")),
                ("carbohydrate_g", daily_carb / Decimal("2")),
                ("total_fat_g", daily_fat / Decimal("2")),
                ("fibre_g", daily_fibre / Decimal("2")),
            ),
            price_reference_id="ref-1",
            min_grams=Decimal("10"),
            max_grams=Decimal("500"),
            functional_role="protein" if slug in protein_slugs else "carb",
        )
        for slug in food_slugs
    )
    meals = (
        PlannedMeal(
            role="main_meal",
            slot_index=0,
            template_id="template-1",
            template_category="lunch",
            foods=foods,
            cost_irr=Decimal(weekly_cost_irr) / Decimal("7"),
            nutrients=(
                ("energy_kcal", daily_calories),
                ("protein_g", daily_protein),
                ("carbohydrate_g", daily_carb),
                ("total_fat_g", daily_fat),
                ("fibre_g", daily_fibre),
            ),
        ),
    )
    days = tuple(
        PlannedDay(
            day_index=i,
            meals=meals,
            cost_irr=Decimal(weekly_cost_irr) / Decimal("7"),
            nutrients=(
                ("energy_kcal", daily_calories),
                ("protein_g", daily_protein),
                ("carbohydrate_g", daily_carb),
                ("total_fat_g", daily_fat),
                ("fibre_g", daily_fibre),
            ),
        )
        for i in range(7)
    )
    return PlannerResult(
        outcome=outcome,
        days=days if outcome == GenerationOutcome.SUCCESS else (),
        weekly_cost_irr=Decimal(weekly_cost_irr)
        if outcome == GenerationOutcome.SUCCESS
        else Decimal("0"),
        reason_codes=(),
    )


def test_compare_plans_calculates_cost_and_macro_gaps() -> None:
    budget_plan = _make_dummy_plan(
        weekly_cost_irr=700_000,
        daily_calories=Decimal("1900"),
        daily_protein=Decimal("130"),
        daily_carb=Decimal("220"),
        daily_fat=Decimal("50"),
        daily_fibre=Decimal("20"),
        food_slugs=("egg", "bread"),
        protein_slugs=("egg",),
    )
    ideal_plan = _make_dummy_plan(
        weekly_cost_irr=3_500_000,
        daily_calories=Decimal("2000"),
        daily_protein=Decimal("160"),
        daily_carb=Decimal("200"),
        daily_fat=Decimal("60"),
        daily_fibre=Decimal("30"),
        food_slugs=("salmon", "quinoa", "beef"),
        protein_slugs=("salmon", "beef"),
    )

    report = compare_plans(
        user_monthly_budget_irr=3_000_000,
        budget_plan_result=budget_plan,
        ideal_plan_result=ideal_plan,
        minimum_feasible_monthly_cost_irr=2_800_000,
    )

    # Weekly to monthly cost conversion: 700_000 * 30 / 7 = 3_000_000
    assert report.budget_plan_monthly_cost_irr == 3_000_000
    # 3_500_000 * 30 / 7 = 15_000_000
    assert report.ideal_plan_monthly_cost_irr == 15_000_000
    assert report.monthly_cost_gap_irr == 15_000_000 - 3_000_000

    # Macro gaps: ideal - budget
    assert report.calorie_gap_kcal_per_day == Decimal("100")
    assert report.protein_gap_g_per_day == Decimal("30")
    assert report.carbohydrate_gap_g_per_day == Decimal("-20")
    assert report.fat_gap_g_per_day == Decimal("10")
    assert report.fibre_gap_g_per_day == Decimal("10")

    # Variety metrics
    assert report.unique_meal_count_budget == 1
    assert report.unique_meal_count_ideal == 1
    assert report.unique_protein_sources_budget == 1
    assert report.unique_protein_sources_ideal == 2

    assert report.meaningful_quality_improvement is True
    assert report.show_ideal_plan is True


def test_compare_plans_handles_budget_insufficient_state() -> None:
    ideal_plan = _make_dummy_plan(weekly_cost_irr=1_200_000)

    report = compare_plans(
        user_monthly_budget_irr=2_000_000,
        budget_plan_result=None,
        ideal_plan_result=ideal_plan,
        minimum_feasible_monthly_cost_irr=3_500_000,
    )

    assert report.budget_plan_monthly_cost_irr is None
    assert report.ideal_plan_monthly_cost_irr == 5_142_857
    assert report.minimum_feasible_monthly_cost_irr == 3_500_000
    assert report.monthly_cost_gap_irr is None
    assert report.protein_gap_g_per_day is None
    assert "BUDGET_INSUFFICIENT_FOR_FEASIBLE_PLAN" in report.reason_codes
    assert report.show_ideal_plan is True


def test_compare_plans_does_not_show_ideal_if_no_meaningful_improvement() -> None:
    plan_a = _make_dummy_plan(weekly_cost_irr=1_000_000, daily_protein=Decimal("150"))
    plan_b = _make_dummy_plan(weekly_cost_irr=1_050_000, daily_protein=Decimal("152"))

    report = compare_plans(
        user_monthly_budget_irr=4_500_000,
        budget_plan_result=plan_a,
        ideal_plan_result=plan_b,
    )

    assert report.meaningful_quality_improvement is False
    assert report.show_ideal_plan is False
