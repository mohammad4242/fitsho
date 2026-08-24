from decimal import Decimal
from uuid import UUID


def _food(
    slug: str,
    roles: tuple[str, ...],
    *,
    kcal: str,
    protein: str = "0",
    carbs: str = "0",
    fat: str = "0",
    price: str = "1000",
    extra: dict[str, str] | None = None,
):
    from app.nutrition.planner_engine import PlannerFood

    nutrients = {
        "energy_kcal": Decimal(kcal),
        "protein_g": Decimal(protein),
        "carbohydrate_g": Decimal(carbs),
        "total_fat_g": Decimal(fat),
        "fibre_g": Decimal("1"),
        **{key: Decimal(value) for key, value in (extra or {}).items()},
    }
    return PlannerFood(
        food_id=slug,
        slug=slug,
        name_fa=slug,
        name_en=slug.replace("-", " ").title(),
        roles=roles,
        nutrients_per_100g=nutrients,
        price_irr_per_gram=Decimal(price),
        price_reference_id=f"price-{slug}",
    )


def _input(**changes: object):
    from app.nutrition.planner_engine import PlannerInput

    values: dict[str, object] = {
        "daily_targets": {
            "goal_calories": Decimal("2000"),
            "protein": Decimal("100"),
            "carbohydrate": Decimal("220"),
            "total_fat": Decimal("60"),
            "fibre": Decimal("25"),
        },
        "micronutrient_targets": {"calcium_mg": Decimal("1000")},
        "micronutrient_upper_limits": {"sodium_mg": Decimal("2300")},
        "daily_minimums": {
            "protein": Decimal("70"),
            "carbohydrate": Decimal("180"),
            "total_fat": Decimal("30"),
        },
        "daily_maximums": {
            "carbohydrate": Decimal("320"),
            "total_fat": Decimal("90"),
            "free_sugar": Decimal("50"),
        },
        "main_meals_per_day": 3,
        "snacks_per_day": 1,
        "weekly_budget_irr": 100_000_000,
        "budget_mode": "strict",
        "excluded_terms": (),
        "liked_food_ids": (),
        "disliked_food_ids": (),
        "dietary_pattern": "omnivore",
        "maximum_meal_repetition_per_week": 2,
    }
    values.update(changes)
    return PlannerInput(**values)  # type: ignore[arg-type]


def test_prepared_recipe_optimizer_changes_raw_inputs_but_returns_cooked_dish() -> None:
    from app.nutrition.planner_engine import PlannerPreparedRecipe, optimize_prepared_recipe
    from app.nutrition.prepared_recipe import (
        PreparedRecipeDefinition,
        PreparedRecipeIngredient,
        PreparedRecipeRatio,
        PreparedRecipeYield,
    )

    beef_id = str(UUID(int=101))
    peas_id = str(UUID(int=102))
    beef = _food(beef_id, ("main_protein",), kcal="200", protein="30", price="1000")
    peas = _food(peas_id, ("main_protein",), kcal="360", protein="20", carbs="60", price="100")
    recipe = PlannerPreparedRecipe(
        revision_id=str(UUID(int=201)),
        name_fa="قیمه",
        name_en="Gheimeh",
        verification_status="draft",
        provenance={"source_name": "Internal recipe source"},
        data_gaps=({"message_fa": "شکاف داخلی", "message_en": "Internal gap"},),
        definition=PreparedRecipeDefinition(
            calculation_version="prepared-recipe-v1",
            ingredients=(
                PreparedRecipeIngredient(
                    food_id=beef_id,
                    reference_grams=Decimal("100"),
                    min_grams=Decimal("80"),
                    max_grams=Decimal("140"),
                    is_required=True,
                ),
                PreparedRecipeIngredient(
                    food_id=peas_id,
                    reference_grams=Decimal("50"),
                    min_grams=Decimal("40"),
                    max_grams=Decimal("70"),
                    is_required=True,
                ),
            ),
            ratios=(
                PreparedRecipeRatio(
                    numerator_food_id=beef_id,
                    denominator_food_id=peas_id,
                    min_ratio=Decimal("1.5"),
                    max_ratio=Decimal("3"),
                ),
            ),
            cooked_yield=PreparedRecipeYield(
                method="proportional_reference_batch",
                reference_input_grams=Decimal("150"),
                final_cooked_yield_grams=Decimal("300"),
            ),
        ),
    )

    economical = optimize_prepared_recipe(
        recipe,
        {beef_id: beef, peas_id: peas},
        target_kcal=Decimal("280"),
        target_protein=Decimal("20"),
        maximum_cost_irr=Decimal("100000"),
    )
    high_protein = optimize_prepared_recipe(
        recipe,
        {beef_id: beef, peas_id: peas},
        target_kcal=Decimal("280"),
        target_protein=Decimal("40"),
        maximum_cost_irr=Decimal("200000"),
    )

    economical_inputs = economical.recipe_snapshot["selected_ingredient_grams"]
    high_protein_inputs = high_protein.recipe_snapshot["selected_ingredient_grams"]
    assert economical.item_kind == "prepared_recipe"
    assert economical.food_id is None
    assert economical.slug == "prepared-gheimeh"
    assert economical.name_fa == "قیمه"
    assert economical.grams > 0
    assert economical.cost_irr <= Decimal("100000")
    assert economical.cost_irr < high_protein.cost_irr
    assert Decimal(high_protein_inputs[beef_id]) >= Decimal(economical_inputs[beef_id])
    assert Decimal("80") <= Decimal(economical_inputs[beef_id]) <= Decimal("140")
    assert Decimal("40") <= Decimal(economical_inputs[peas_id]) <= Decimal("70")
    economical_ratio = Decimal(economical_inputs[beef_id]) / Decimal(economical_inputs[peas_id])
    assert Decimal("1.5") <= economical_ratio <= Decimal("3")
    assert Decimal(high_protein_inputs[beef_id]) / Decimal(high_protein_inputs[peas_id]) <= 3
    assert high_protein.recipe_snapshot["calculation_version"] == "prepared-recipe-v1"
    assert high_protein.recipe_snapshot["verification_status"] == "draft"
    assert high_protein.recipe_snapshot["provenance"] == {"source_name": "Internal recipe source"}
    assert high_protein.recipe_snapshot["data_gaps"] == [
        {"message_fa": "شکاف داخلی", "message_en": "Internal gap"}
    ]


def test_prepared_recipe_optimizer_rejects_an_infinite_budget() -> None:
    import pytest

    from app.nutrition.planner_engine import PlannerPreparedRecipe, optimize_prepared_recipe
    from app.nutrition.prepared_recipe import (
        PreparedRecipeDefinition,
        PreparedRecipeIngredient,
        PreparedRecipeYield,
    )

    food = _food("recipe-food", ("main_protein",), kcal="200", protein="30", price="100")
    recipe = PlannerPreparedRecipe(
        revision_id=str(UUID(int=301)),
        name_fa="غذای تست",
        name_en="Test recipe",
        definition=PreparedRecipeDefinition(
            calculation_version="prepared-recipe-v1",
            ingredients=(
                PreparedRecipeIngredient(
                    food_id=food.food_id,
                    reference_grams=Decimal("100"),
                    min_grams=Decimal("80"),
                    max_grams=Decimal("120"),
                    is_required=True,
                ),
            ),
            ratios=(),
            cooked_yield=PreparedRecipeYield(
                method="proportional_reference_batch",
                reference_input_grams=Decimal("100"),
                final_cooked_yield_grams=Decimal("145"),
            ),
        ),
    )

    with pytest.raises(ValueError, match="finite"):
        optimize_prepared_recipe(
            recipe,
            {food.food_id: food},
            target_kcal=Decimal("200"),
            target_protein=Decimal("30"),
            maximum_cost_irr=Decimal("Infinity"),
        )


def test_weekly_budget_repairs_prepared_recipes_to_cheaper_valid_variants() -> None:
    from app.nutrition.planner_engine import (
        GenerationOutcome,
        PlannerMealTemplate,
        PlannerPreparedRecipe,
        plan_week,
    )
    from app.nutrition.prepared_recipe import (
        PreparedRecipeDefinition,
        PreparedRecipeIngredient,
        PreparedRecipeRatio,
        PreparedRecipeYield,
    )

    beef = _food("budget-beef", ("main_protein",), kcal="200", protein="30", price="1000")
    peas = _food(
        "budget-peas",
        ("main_protein",),
        kcal="360",
        protein="20",
        carbs="60",
        price="100",
    )
    recipe = PlannerPreparedRecipe(
        revision_id=str(UUID(int=401)),
        name_fa="قیمه بودجه‌ای",
        name_en="Budget Gheimeh",
        definition=PreparedRecipeDefinition(
            calculation_version="prepared-recipe-v1",
            ingredients=(
                PreparedRecipeIngredient(
                    food_id=beef.food_id,
                    reference_grams=Decimal("100"),
                    min_grams=Decimal("80"),
                    max_grams=Decimal("140"),
                    is_required=True,
                ),
                PreparedRecipeIngredient(
                    food_id=peas.food_id,
                    reference_grams=Decimal("50"),
                    min_grams=Decimal("40"),
                    max_grams=Decimal("70"),
                    is_required=True,
                ),
            ),
            ratios=(
                PreparedRecipeRatio(
                    numerator_food_id=beef.food_id,
                    denominator_food_id=peas.food_id,
                    min_ratio=Decimal("1.5"),
                    max_ratio=Decimal("3"),
                ),
            ),
            cooked_yield=PreparedRecipeYield(
                method="proportional_reference_batch",
                reference_input_grams=Decimal("150"),
                final_cooked_yield_grams=Decimal("300"),
            ),
        ),
    )
    template = PlannerMealTemplate(
        meal_id="budget-recipe-template",
        name_fa="قیمه",
        name_en="Gheimeh",
        category="lunch",
        items=(),
        prepared_recipe=recipe,
    )
    day = (
        ("main_meal", template.meal_id, "lunch"),
        ("free_meal", None, "dinner"),
    )
    inputs = _input(
        daily_targets={"goal_calories": Decimal("500")},
        micronutrient_targets={},
        micronutrient_upper_limits={},
        daily_minimums={},
        daily_maximums={},
        main_meals_per_day=2,
        snacks_per_day=0,
        weekly_budget_irr=800_000,
        template_schedule=(day,) * 7,
    )

    result = plan_week(inputs, (beef, peas), (template,))

    assert result.outcome is GenerationOutcome.SUCCESS
    assert result.weekly_cost_irr <= Decimal(inputs.weekly_budget_irr)
    recipes = [
        meal.foods[0] for day_result in result.days for meal in day_result.meals if meal.foods
    ]
    assert all(recipe_food.item_kind == "prepared_recipe" for recipe_food in recipes)
    for recipe_food in recipes:
        snapshot = recipe_food.recipe_snapshot
        assert snapshot is not None
        quantities = snapshot["selected_ingredient_grams"]
        beef_grams = Decimal(quantities[beef.food_id])
        peas_grams = Decimal(quantities[peas.food_id])
        assert Decimal("80") <= beef_grams <= Decimal("140")
        assert Decimal("40") <= peas_grams <= Decimal("70")
        assert Decimal("1.5") <= beef_grams / peas_grams <= Decimal("3")


def _catalogue():
    return (
        _food("chicken", ("main_protein",), kcal="165", protein="31", fat="3.6"),
        _food(
            "lentils",
            ("main_protein",),
            kcal="116",
            protein="9",
            carbs="20",
            extra={"calcium_mg": "19"},
        ),
        _food("rice", ("main_staple",), kcal="360", protein="7", carbs="79"),
        _food("potato", ("main_staple",), kcal="77", protein="2", carbs="17"),
        _food(
            "yogurt",
            ("snack", "flexible"),
            kcal="61",
            protein="3.5",
            carbs="4.7",
            fat="3.3",
            extra={"calcium_mg": "121"},
        ),
        _food("olive-oil", ("flexible",), kcal="884", fat="100"),
    )


def _meal_templates():
    from app.nutrition.planner_engine import PlannerMealIngredient, PlannerMealTemplate

    def item(
        food_id: str,
        reference: str,
        minimum: str,
        maximum: str,
        role: str,
        *,
        required: bool = True,
    ) -> PlannerMealIngredient:
        return PlannerMealIngredient(
            food_id=food_id,
            reference_grams=Decimal(reference),
            min_grams=Decimal(minimum),
            max_grams=Decimal(maximum),
            is_required=required,
            functional_role=role,
        )

    return (
        PlannerMealTemplate(
            meal_id="lunch-template",
            name_fa="مرغ و برنج",
            name_en="Chicken and rice",
            category="lunch",
            items=(
                item("chicken", "150", "80", "220", "protein"),
                item("rice", "80", "50", "140", "carbohydrate"),
                item("olive-oil", "5", "2", "10", "fat", required=False),
            ),
        ),
        PlannerMealTemplate(
            meal_id="dinner-template",
            name_fa="عدس و سیب‌زمینی",
            name_en="Lentils and potato",
            category="dinner",
            items=(
                item("lentils", "180", "100", "300", "protein"),
                item("potato", "250", "150", "400", "carbohydrate"),
                item("yogurt", "100", "50", "200", "micronutrient_source", required=False),
            ),
        ),
        PlannerMealTemplate(
            meal_id="post-workout-template",
            name_fa="مرغ و سیب‌زمینی",
            name_en="Chicken and potato",
            category="post_workout",
            items=(
                item("chicken", "120", "80", "220", "protein"),
                item("potato", "250", "150", "400", "carbohydrate"),
            ),
        ),
        PlannerMealTemplate(
            meal_id="snack-template",
            name_fa="ماست",
            name_en="Yogurt",
            category="snack",
            items=(item("yogurt", "200", "100", "350", "protein"),),
        ),
    )


def test_planner_uses_only_catalogue_templates_and_keeps_every_item_in_bounds() -> None:
    from app.nutrition.planner_engine import GenerationOutcome, plan_week

    templates = _meal_templates()
    result = plan_week(_input(), _catalogue(), meal_templates=templates)

    assert result.outcome is GenerationOutcome.SUCCESS
    bounds = {
        (template.meal_id, item.food_id): (item.min_grams, item.max_grams)
        for template in templates
        for item in template.items
    }
    assert all(meal.template_id for day in result.days for meal in day.meals)
    assert all(
        bounds[(meal.template_id, food.food_id)][0]
        <= food.grams
        <= bounds[(meal.template_id, food.food_id)][1]
        for day in result.days
        for meal in day.meals
        for food in meal.foods
    )


def test_required_exclusion_removes_whole_template_without_arbitrary_substitution() -> None:
    from app.nutrition.planner_engine import plan_week

    result = plan_week(
        _input(excluded_terms=("chicken",)),
        _catalogue(),
        meal_templates=_meal_templates(),
    )

    assert all(
        meal.template_id != "lunch-template" and all(food.slug != "chicken" for food in meal.foods)
        for day in result.days
        for meal in day.meals
    )


def test_planner_creates_exact_user_selected_slots_for_seven_days() -> None:
    from app.nutrition.planner_engine import GenerationOutcome, plan_week

    result = plan_week(
        _input(main_meals_per_day=2, snacks_per_day=2),
        _catalogue(),
        _meal_templates(),
    )

    assert result.outcome is GenerationOutcome.SUCCESS
    assert len(result.days) == 7
    assert all(sum(meal.role == "main_meal" for meal in day.meals) == 2 for day in result.days)
    assert all(sum(meal.role == "snack" for meal in day.meals) == 2 for day in result.days)


def test_planner_uses_exact_program_schedule_and_redistributes_around_free_meal() -> None:
    from app.nutrition.planner_engine import GenerationOutcome, plan_week

    normal = (
        ("main_meal", "lunch-template", "lunch"),
        ("main_meal", "dinner-template", "dinner"),
        ("snack", "snack-template", "snack"),
    )
    friday = (
        ("free_meal", None, "lunch"),
        ("main_meal", "dinner-template", "dinner"),
        ("snack", "snack-template", "snack"),
    )
    schedule = (normal, normal, normal, normal, normal, normal, friday)
    inputs = _input(main_meals_per_day=2, template_schedule=schedule)

    result = plan_week(inputs, _catalogue(), _meal_templates())

    assert result.outcome is GenerationOutcome.SUCCESS
    assert [[meal.template_id for meal in day.meals] for day in result.days[:6]] == [
        ["lunch-template", "dinner-template", "snack-template"]
    ] * 6
    assert [meal.template_id for meal in result.days[6].meals] == [
        None,
        "dinner-template",
        "snack-template",
    ]
    assert result.days[6].meals[0].foods == ()
    assert inputs.daily_targets["goal_calories"] == Decimal("2000")


def test_planner_is_deterministic_and_controls_repetition() -> None:
    from app.nutrition.planner_engine import plan_week

    first = plan_week(_input(), _catalogue(), _meal_templates())
    second = plan_week(_input(), tuple(reversed(_catalogue())), tuple(reversed(_meal_templates())))

    assert first == second
    proteins = [
        meal.foods[0].slug for day in first.days for meal in day.meals if meal.role == "main_meal"
    ]
    assert {"chicken", "lentils"} <= set(proteins)


def test_allergy_filter_is_hard_and_role_specific() -> None:
    from app.nutrition.planner_engine import plan_week

    result = plan_week(_input(excluded_terms=("chicken",)), _catalogue(), _meal_templates())

    assert all(
        food.slug != "chicken" for day in result.days for meal in day.meals for food in meal.foods
    )
    assert all(
        food.roles == ("snack", "flexible")
        for day in result.days
        for meal in day.meals
        if meal.role == "snack"
        for food in meal.foods
    )


def test_missing_required_price_coverage_returns_structured_outcome() -> None:
    from app.nutrition.planner_engine import GenerationOutcome, plan_week

    foods = tuple(food for food in _catalogue() if food.roles != ("main_staple",))
    result = plan_week(_input(), foods, _meal_templates())

    assert result.outcome is GenerationOutcome.LIVE_PRICE_UNAVAILABLE
    assert result.reason_codes == ("INSUFFICIENT_PRICE_COVERAGE",)
    assert result.days == ()


def test_strict_budget_is_hard_and_flexible_budget_has_a_versioned_cap() -> None:
    from app.nutrition.planner_engine import GenerationOutcome, plan_week

    strict = plan_week(_input(weekly_budget_irr=1_000), _catalogue(), _meal_templates())
    flexible = plan_week(
        _input(weekly_budget_irr=20_000_000, budget_mode="flexible"),
        _catalogue(),
        _meal_templates(),
    )

    assert strict.outcome is GenerationOutcome.INFEASIBLE
    assert "STRICT_BUDGET_EXCEEDED" in strict.reason_codes
    assert flexible.outcome is GenerationOutcome.SUCCESS
    assert flexible.budget_status in {"within_budget", "flexible_overage"}


def test_micronutrients_affect_selection_and_repair_is_bounded() -> None:
    from app.nutrition.planner_engine import plan_week

    result = plan_week(_input(), _catalogue(), _meal_templates())

    assert result.repair_actions
    assert len(result.repair_actions) <= 3
    assert result.nutrient_comparisons["calcium_mg"].planned > 0


def test_upper_limit_violation_never_creates_a_successful_plan() -> None:
    from dataclasses import replace

    from app.nutrition.planner_engine import GenerationOutcome, plan_week

    salty = _food(
        "salty-chicken",
        ("main_protein",),
        kcal="165",
        protein="31",
        extra={"sodium_mg": "10000"},
    )
    foods = (salty, *_catalogue()[2:])
    lunch, *other_templates = _meal_templates()
    salty_lunch = replace(
        lunch,
        items=(replace(lunch.items[0], food_id="salty-chicken"), *lunch.items[1:]),
    )
    result = plan_week(_input(), foods, (salty_lunch, *other_templates))

    assert result.outcome is GenerationOutcome.INFEASIBLE
    assert "NUTRIENT_UPPER_LIMIT_EXCEEDED" in result.reason_codes


def test_result_snapshots_are_immutable() -> None:
    from dataclasses import FrozenInstanceError

    import pytest

    from app.nutrition.planner_engine import plan_week

    result = plan_week(_input(), _catalogue(), _meal_templates())
    with pytest.raises(FrozenInstanceError):
        result.weekly_cost_irr = Decimal("0")  # type: ignore[misc]


def test_dietary_pattern_is_a_hard_candidate_filter() -> None:
    from app.nutrition.planner_engine import GenerationOutcome, PlannerFood, plan_week

    foods = tuple(
        PlannerFood(
            **{
                **food.__dict__,
                "dietary_patterns": (
                    ("omnivore",) if food.slug == "chicken" else ("omnivore", "vegan")
                ),
            }
        )
        for food in _catalogue()
    )

    result = plan_week(_input(dietary_pattern="vegan", daily_minimums={}), foods, _meal_templates())

    assert result.outcome is GenerationOutcome.SUCCESS
    assert all(
        food.slug != "chicken" for day in result.days for meal in day.meals for food in meal.foods
    )


def test_macro_floor_failure_is_target_infeasible_after_full_validation() -> None:
    from app.nutrition.planner_engine import GenerationOutcome, plan_week

    result = plan_week(
        _input(daily_minimums={"protein": Decimal("900")}),
        _catalogue(),
        _meal_templates(),
    )

    assert result.outcome is GenerationOutcome.TARGET_INFEASIBLE
    assert "MACRONUTRIENT_FLOOR_NOT_MET" in result.reason_codes


def test_missing_supported_nutrient_data_is_reported_not_treated_as_zero() -> None:
    from app.nutrition.planner_engine import plan_week

    result = plan_week(_input(), _catalogue(), _meal_templates())

    comparison = result.nutrient_comparisons["free_sugar"]
    assert comparison.status == "data_incomplete"
    assert comparison.data_confidence == "low"
    assert "NUTRIENT_DATA_INCOMPLETE" in result.warning_codes


def test_micronutrient_density_influences_initial_candidate_order() -> None:
    from dataclasses import replace

    from app.nutrition.planner_engine import plan_week

    enriched = _food(
        "calcium-lentils",
        ("main_protein",),
        kcal="116",
        protein="9",
        carbs="20",
        extra={"calcium_mg": "500"},
    )
    foods = (*_catalogue(), enriched)
    lunch, *templates = _meal_templates()
    calcium_template = replace(
        lunch,
        meal_id="calcium-template",
        items=(replace(lunch.items[0], food_id="calcium-lentils"), *lunch.items[1:]),
    )

    result = plan_week(_input(), foods, (lunch, calcium_template, *templates))

    first_protein = result.days[0].meals[0].foods[0]
    assert first_protein.slug == "calcium-lentils"
