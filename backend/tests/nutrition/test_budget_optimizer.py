from decimal import Decimal

from app.nutrition.budget_optimizer import BudgetRepairAction, optimize_weekly_budget
from app.nutrition.candidate_selection import evaluate_candidate, select_best_candidate
from app.nutrition.enums import NutritionDietStyle
from app.nutrition.models import NutritionProgram
from app.nutrition.planner_engine import (
    EligibleMealTemplate,
    GenerationOutcome,
    NutrientComparison,
    PlannedDay,
    PlannedFood,
    PlannedMeal,
    PlannerFood,
    PlannerInput,
    PlannerMealIngredient,
    PlannerMealTemplate,
    PlannerResult,
)
from app.nutrition.planner_policy import PlannerPolicy
from app.nutrition.program_selection import ProgramCandidate


def _food(
    food_id: str,
    *,
    kcal: str = "200",
    protein: str = "20",
    carbs: str = "20",
    fat: str = "5",
    price: str = "100",
    dietary_patterns: tuple[str, ...] = ("omnivore",),
    price_reference_id: str | None = None,
) -> PlannerFood:
    return PlannerFood(
        food_id=food_id,
        slug=food_id,
        name_fa=food_id,
        name_en=food_id,
        roles=("main_protein",),
        nutrients_per_100g={
            "energy_kcal": Decimal(kcal),
            "protein_g": Decimal(protein),
            "carbohydrate_g": Decimal(carbs),
            "total_fat_g": Decimal(fat),
            "fibre_g": Decimal("2"),
        },
        price_irr_per_gram=Decimal(price),
        price_reference_id=price_reference_id or f"price-{food_id}",
        dietary_patterns=dietary_patterns,
    )


def _template(template_id: str, food_id: str, *, category: str = "lunch") -> PlannerMealTemplate:
    return PlannerMealTemplate(
        meal_id=template_id,
        name_fa=template_id,
        name_en=template_id,
        category=category,
        items=(
            PlannerMealIngredient(
                food_id=food_id,
                reference_grams=Decimal("100"),
                min_grams=Decimal("10"),
                max_grams=Decimal("300"),
                is_required=True,
                functional_role="protein",
            ),
        ),
    )


def _eligible(template: PlannerMealTemplate, food: PlannerFood) -> EligibleMealTemplate:
    return EligibleMealTemplate(template=template, items=((template.items[0], food),))


def _input(*, budget: int, budget_mode: str = "strict", repetition: int = 7) -> PlannerInput:
    return PlannerInput(
        daily_targets={
            "goal_calories": Decimal("200"),
            "protein": Decimal("20"),
            "carbohydrate": Decimal("20"),
            "total_fat": Decimal("5"),
        },
        micronutrient_targets={},
        micronutrient_upper_limits={},
        daily_minimums={
            "protein": Decimal("15"),
            "carbohydrate": Decimal("15"),
            "total_fat": Decimal("3"),
        },
        daily_maximums={},
        main_meals_per_day=2,
        snacks_per_day=0,
        weekly_budget_irr=budget,
        budget_mode=budget_mode,
        excluded_terms=(),
        liked_food_ids=(),
        disliked_food_ids=(),
        dietary_pattern="omnivore",
        maximum_meal_repetition_per_week=repetition,
    )


def _planned_food(food: PlannerFood) -> PlannedFood:
    grams = Decimal("100")
    return PlannedFood(
        food_id=food.food_id,
        slug=food.slug,
        name_fa=food.name_fa,
        name_en=food.name_en,
        roles=food.roles,
        grams=grams,
        cost_irr=food.price_irr_per_gram * grams,
        nutrients=tuple(
            sorted(
                (code, value * grams / Decimal("100"))
                for code, value in food.nutrients_per_100g.items()
            )
        ),
        price_reference_id=food.price_reference_id,
        min_grams=Decimal("10"),
        max_grams=Decimal("300"),
        functional_role="protein",
    )


def _days(template: PlannerMealTemplate, food: PlannerFood) -> tuple[PlannedDay, ...]:
    planned = _planned_food(food)
    nutrients = tuple(sorted(dict(planned.nutrients).items()))
    meals = tuple(
        PlannedMeal(
            role="main_meal",
            slot_index=0,
            template_id=template.meal_id,
            template_category=template.category,
            foods=(planned,),
            cost_irr=planned.cost_irr,
            nutrients=nutrients,
        )
        for _ in range(7)
    )
    return tuple(
        PlannedDay(
            day_index=day_index,
            meals=(meal,),
            cost_irr=meal.cost_irr,
            nutrients=meal.nutrients,
        )
        for day_index, meal in enumerate(meals)
    )


def test_over_budget_candidate_is_repaired_with_a_cheaper_eligible_template() -> None:
    expensive_food = _food("expensive-food", price="100")
    cheap_food = _food("cheap-food", price="10")
    expensive = _template("expensive-template", expensive_food.food_id)
    cheap = _template("cheap-template", cheap_food.food_id)

    result = optimize_weekly_budget(
        days=_days(expensive, expensive_food),
        inputs=_input(budget=10_000),
        eligible_templates=(_eligible(expensive, expensive_food), _eligible(cheap, cheap_food)),
        policy=PlannerPolicy(maximum_budget_repair_iterations=10),
    )

    assert result.failure_code is None
    assert result.final_cost_irr <= Decimal("10000")
    assert len(result.repair_actions) == 7
    assert all(action.action_type == "replace_template" for action in result.repair_actions)
    assert all(
        meal.template_id == cheap.meal_id for day in result.days for meal in day.meals if meal.foods
    )
    assert all(action.saved_irr > 0 for action in result.repair_actions)


def test_strict_and_flexible_budget_caps_are_not_widened() -> None:
    expensive_food = _food("expensive-food", price="100")
    cheap_food = _food("cheap-food", price="10")
    expensive = _template("expensive-template", expensive_food.food_id)
    cheap = _template("cheap-template", cheap_food.food_id)
    templates = (_eligible(expensive, expensive_food), _eligible(cheap, cheap_food))

    strict = optimize_weekly_budget(
        days=_days(expensive, expensive_food),
        inputs=_input(budget=10_000),
        eligible_templates=templates,
        policy=PlannerPolicy(maximum_budget_repair_iterations=10),
    )
    flexible = optimize_weekly_budget(
        days=_days(expensive, expensive_food),
        inputs=_input(budget=4_000, budget_mode="flexible"),
        eligible_templates=templates,
        policy=PlannerPolicy(maximum_budget_repair_iterations=10),
    )

    assert strict.failure_code is None
    assert strict.final_cost_irr <= Decimal("10000")
    assert flexible.failure_code == "FLEXIBLE_BUDGET_NO_FEASIBLE_REPAIR"
    assert flexible.final_cost_irr > Decimal("4000") * Decimal("1.15")
    assert flexible.diagnostics["user_weekly_budget_irr"] == "4000"


def test_optimizer_does_not_use_incompatible_or_invalid_price_templates() -> None:
    expensive_food = _food("expensive-food", price="100")
    unsafe_food = _food("unsafe-food", price="1", dietary_patterns=("vegan",))
    invalid_price_food = _food("invalid-price-food", price="1", price_reference_id="unavailable")
    expensive = _template("expensive-template", expensive_food.food_id)
    unsafe = _template("unsafe-template", unsafe_food.food_id)
    invalid_price = _template("invalid-price-template", invalid_price_food.food_id)

    result = optimize_weekly_budget(
        days=_days(expensive, expensive_food),
        inputs=_input(budget=10_000),
        eligible_templates=(
            _eligible(expensive, expensive_food),
            _eligible(unsafe, unsafe_food),
            _eligible(invalid_price, invalid_price_food),
        ),
        policy=PlannerPolicy(maximum_budget_repair_iterations=2),
    )

    assert result.failure_code == "STRICT_BUDGET_NO_FEASIBLE_REPAIR"
    assert all(
        meal.template_id == expensive.meal_id
        for day in result.days
        for meal in day.meals
        if meal.foods
    )


def test_optimizer_recomputes_day_nutrients_after_a_repair() -> None:
    expensive_food = _food("expensive-food", price="100")
    cheap_food = _food("cheap-food", kcal="150", protein="15", carbs="15", fat="4", price="10")
    expensive = _template("expensive-template", expensive_food.food_id)
    cheap = _template("cheap-template", cheap_food.food_id)

    result = optimize_weekly_budget(
        days=_days(expensive, expensive_food),
        inputs=_input(budget=10_000),
        eligible_templates=(_eligible(expensive, expensive_food), _eligible(cheap, cheap_food)),
        policy=PlannerPolicy(maximum_budget_repair_iterations=10),
    )

    assert result.failure_code is None
    for day in result.days:
        assert day.cost_irr == sum((meal.cost_irr for meal in day.meals), Decimal("0"))
        assert dict(day.nutrients) == {
            code: value for meal in day.meals for code, value in meal.nutrients
        }
        for meal in day.meals:
            assert dict(meal.nutrients) == {
                code: value for food in meal.foods for code, value in food.nutrients
            }


def test_optimizer_respects_repetition_when_repairing() -> None:
    expensive_food = _food("expensive-food", price="100")
    cheap_foods = tuple(_food(f"cheap-food-{index}", price="10") for index in range(1, 4))
    expensive = _template("expensive-template", expensive_food.food_id)
    cheap_templates = tuple(
        _template(f"cheap-template-{index}", food.food_id)
        for index, food in enumerate(cheap_foods, start=1)
    )

    result = optimize_weekly_budget(
        days=_days(expensive, expensive_food),
        inputs=_input(budget=10_000, repetition=2),
        eligible_templates=(
            _eligible(expensive, expensive_food),
            *(
                _eligible(template, food)
                for template, food in zip(cheap_templates, cheap_foods, strict=True)
            ),
        ),
        policy=PlannerPolicy(maximum_budget_repair_iterations=10),
    )

    assert result.failure_code is None
    usage = {
        template_id: sum(
            meal.template_id == template_id for day in result.days for meal in day.meals
        )
        for template_id in {meal.template_id for day in result.days for meal in day.meals}
    }
    assert all(count <= 2 for count in usage.values())


def test_optimizer_is_deterministic_for_the_same_input() -> None:
    expensive_food = _food("expensive-food", price="100")
    cheap_food = _food("cheap-food", price="10")
    expensive = _template("expensive-template", expensive_food.food_id)
    cheap = _template("cheap-template", cheap_food.food_id)
    kwargs = {
        "days": _days(expensive, expensive_food),
        "inputs": _input(budget=10_000),
        "eligible_templates": (_eligible(expensive, expensive_food), _eligible(cheap, cheap_food)),
        "policy": PlannerPolicy(maximum_budget_repair_iterations=10),
    }

    assert optimize_weekly_budget(**kwargs) == optimize_weekly_budget(**kwargs)


def test_impossible_strict_budget_has_explicit_failure_and_minimum_cost_diagnostics() -> None:
    expensive_food = _food("expensive-food", price="100")
    expensive = _template("expensive-template", expensive_food.food_id)

    result = optimize_weekly_budget(
        days=_days(expensive, expensive_food),
        inputs=_input(budget=1_000),
        eligible_templates=(_eligible(expensive, expensive_food),),
        policy=PlannerPolicy(maximum_budget_repair_iterations=2),
    )

    assert result.failure_code == "STRICT_BUDGET_NO_FEASIBLE_REPAIR"
    assert result.diagnostics["minimum_feasible_weekly_cost_irr"] == "61000"
    assert result.diagnostics["budget_gap_irr"] == "60000"
    assert result.diagnostics["feasibility_search_exhaustive"] == "false"


def test_candidate_selection_prefers_nutrition_over_a_cheaper_repaired_plan() -> None:
    good_program = NutritionProgram(
        code="GOOD",
        slug="good",
        diet_style=NutritionDietStyle.BALANCED_IRANIAN,
    )
    cheap_program = NutritionProgram(
        code="CHEAP",
        slug="cheap",
        diet_style=NutritionDietStyle.ECONOMY,
    )
    good_proposal = ProgramCandidate(
        program=good_program,
        preferred_style=True,
        preconstruction_rank=0,
    )
    cheap_proposal = ProgramCandidate(
        program=cheap_program,
        preferred_style=False,
        preconstruction_rank=1,
    )

    def result(cost: str, planned: str, repairs: int) -> PlannerResult:
        comparisons = {
            code: NutrientComparison(
                preferred=Decimal(preferred),
                minimum_or_maximum=None,
                planned=Decimal(planned if code == "goal_calories" else "20"),
                difference_from_preferred=Decimal("0"),
                difference_from_limit=None,
                status="within_target",
            )
            for code, preferred in (
                ("goal_calories", "200"),
                ("protein", "20"),
                ("carbohydrate", "20"),
                ("total_fat", "5"),
            )
        }
        return PlannerResult(
            outcome=GenerationOutcome.SUCCESS,
            reason_codes=("SAFE_FEASIBLE_DRAFT_GENERATED",),
            weekly_cost_irr=Decimal(cost),
            nutrient_comparisons=comparisons,
            budget_repair_actions=tuple(
                BudgetRepairAction(
                    day_index=0,
                    role="main_meal",
                    slot_index=0,
                    action_type="replace_template",
                    before_cost_irr=Decimal("2"),
                    after_cost_irr=Decimal("1"),
                    saved_irr=Decimal("1"),
                    reason_code="test",
                )
                for _ in range(repairs)
            ),
        )

    good = evaluate_candidate(
        good_proposal,
        result("10000", "200", 1),
        weekly_budget_irr=Decimal("20000"),
    )
    cheap = evaluate_candidate(
        cheap_proposal,
        result("1000", "100", 0),
        weekly_budget_irr=Decimal("20000"),
    )

    assert select_best_candidate((good, cheap)).selected == good
