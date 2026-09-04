from dataclasses import replace
from decimal import Decimal

from app.nutrition.candidate_selection import evaluate_candidate
from app.nutrition.enums import NutritionDietStyle
from app.nutrition.food_constraints import normalize_food_constraints
from app.nutrition.models import NutritionProgram
from app.nutrition.planner_engine import (
    EligibleMealTemplate,
    GenerationOutcome,
    PlannerFood,
    PlannerInput,
    PlannerMealIngredient,
    PlannerMealTemplate,
    PlannerPreparedRecipe,
    PlannerResult,
    _eligible_templates,
    plan_week,
)
from app.nutrition.prepared_recipe import (
    PreparedRecipeDefinition,
    PreparedRecipeIngredient,
    PreparedRecipeYield,
)
from app.nutrition.program_selection import ProgramCandidate
from app.nutrition.template_substitution import (
    SubstitutionAction,
    SubstitutionContext,
    rank_template_substitutes,
)


def _food(
    slug: str,
    *,
    kcal: str = "200",
    protein: str = "20",
    carbs: str = "20",
    fat: str = "5",
    dietary_patterns: tuple[str, ...] = ("omnivore", "vegetarian", "vegan"),
    allergen_tags: tuple[str, ...] = (),
    allergen_metadata_verified: bool = False,
) -> PlannerFood:
    return PlannerFood(
        food_id=slug,
        slug=slug,
        name_fa=slug,
        name_en=slug,
        roles=("main_protein",),
        nutrients_per_100g={
            "energy_kcal": Decimal(kcal),
            "protein_g": Decimal(protein),
            "carbohydrate_g": Decimal(carbs),
            "total_fat_g": Decimal(fat),
            "fibre_g": Decimal("2"),
        },
        price_irr_per_gram=Decimal("10"),
        price_reference_id=f"price-{slug}",
        dietary_patterns=dietary_patterns,
        allergen_tags=allergen_tags,
        allergen_metadata_verified=allergen_metadata_verified,
    )


def _template(
    meal_id: str,
    category: str,
    food_id: str,
    *,
    reference: str = "100",
    minimum: str = "10",
    maximum: str = "300",
    verification_status: str = "verified",
) -> PlannerMealTemplate:
    return PlannerMealTemplate(
        meal_id=meal_id,
        name_fa=meal_id,
        name_en=meal_id,
        category=category,
        verification_status=verification_status,
        items=(
            PlannerMealIngredient(
                food_id=food_id,
                reference_grams=Decimal(reference),
                min_grams=Decimal(minimum),
                max_grams=Decimal(maximum),
                is_required=True,
                functional_role="protein",
            ),
        ),
    )


def _eligible(template: PlannerMealTemplate, food: PlannerFood) -> EligibleMealTemplate:
    return EligibleMealTemplate(template=template, items=((template.items[0], food),))


def _input(
    *, dietary_pattern: str = "omnivore", excluded_terms: tuple[str, ...] = ()
) -> PlannerInput:
    return PlannerInput(
        daily_targets={
            "goal_calories": Decimal("200"),
            "protein": Decimal("20"),
            "carbohydrate": Decimal("20"),
            "total_fat": Decimal("5"),
        },
        micronutrient_targets={},
        micronutrient_upper_limits={},
        daily_minimums={},
        daily_maximums={},
        main_meals_per_day=2,
        snacks_per_day=0,
        weekly_budget_irr=1_000_000,
        budget_mode="strict",
        excluded_terms=excluded_terms,
        liked_food_ids=(),
        disliked_food_ids=(),
        dietary_pattern=dietary_pattern,
        maximum_meal_repetition_per_week=7,
    )


def _schedule(meal_id: str) -> tuple[tuple[tuple[str, str | None, str], ...], ...]:
    return tuple((("main_meal", meal_id, "lunch"),) for _ in range(7))


def test_rank_template_substitutes_is_category_safe_and_deterministic() -> None:
    requested_food = _food("requested")
    requested = _template("requested", "lunch", requested_food.food_id)
    lunch_a = _template("lunch-a", "lunch", "lunch-a")
    lunch_b = _template("lunch-b", "lunch", "lunch-b")
    breakfast = _template("breakfast", "breakfast", "breakfast")
    candidates = (
        _eligible(breakfast, _food("breakfast")),
        _eligible(lunch_b, _food("lunch-b", kcal="205", protein="20")),
        _eligible(lunch_a, _food("lunch-a", kcal="200", protein="20")),
    )

    context = SubstitutionContext(
        slot_category="lunch",
        target_kcal=Decimal("200"),
        target_protein=Decimal("20"),
    )

    ranked = rank_template_substitutes(requested, candidates, context)

    assert [item.template.meal_id for item in ranked] == ["lunch-a", "lunch-b"]
    assert [
        item.template.meal_id
        for item in rank_template_substitutes(requested, tuple(reversed(candidates)), context)
    ] == ["lunch-a", "lunch-b"]


def test_rank_template_substitutes_skips_a_repetition_capped_candidate() -> None:
    requested = _template("requested", "lunch", "requested")
    first = _template("lunch-a", "lunch", "lunch-a")
    second = _template("lunch-b", "lunch", "lunch-b")
    context = SubstitutionContext(
        slot_category="lunch",
        target_kcal=Decimal("200"),
        target_protein=Decimal("20"),
        template_usage=(("lunch-a", 2),),
        maximum_repetition=2,
    )

    ranked = rank_template_substitutes(
        requested,
        (_eligible(first, _food("lunch-a")), _eligible(second, _food("lunch-b"))),
        context,
    )

    assert [item.template.meal_id for item in ranked] == ["lunch-b"]


def test_original_available_is_used_without_a_substitution() -> None:
    food = _food("safe")
    original = _template("safe-lunch", "lunch", food.food_id)
    inputs = _input()
    inputs = replace(inputs, template_schedule=_schedule(original.meal_id))

    result = plan_week(inputs, (food,), (original,))

    assert result.outcome.value == "success"
    assert result.substitution_actions == ()
    assert all(meal.template_id == original.meal_id for day in result.days for meal in day.meals)


def test_incompatible_scheduled_meal_uses_an_already_eligible_substitute() -> None:
    meat = _food("chicken", dietary_patterns=("omnivore",))
    vegetarian = _food("lentils", dietary_patterns=("vegetarian", "vegan"))
    requested = _template("meat-lunch", "lunch", meat.food_id)
    replacement = _template("lentil-lunch", "lunch", vegetarian.food_id)
    inputs = _input(dietary_pattern="vegetarian")
    inputs = replace(inputs, template_schedule=_schedule(requested.meal_id))

    result = plan_week(inputs, (meat, vegetarian), (requested, replacement))

    assert result.outcome.value == "success"
    assert all(meal.template_id == replacement.meal_id for day in result.days for meal in day.meals)
    assert len(result.substitution_actions) == 7
    assert all(
        action.requested_template_id == requested.meal_id for action in result.substitution_actions
    )
    assert all(
        action.replacement_template_id == replacement.meal_id
        for action in result.substitution_actions
    )


def test_excluded_food_does_not_reenter_through_substitution() -> None:
    requested_food = _food("peanut-meal", dietary_patterns=("omnivore",))
    excluded_food = _food("peanut", dietary_patterns=("omnivore",))
    safe_food = _food("rice", dietary_patterns=("omnivore",))
    requested = _template("requested", "lunch", requested_food.food_id)
    excluded = _template("excluded", "lunch", excluded_food.food_id)
    safe = _template("safe", "lunch", safe_food.food_id)
    inputs = _input(excluded_terms=("peanut",))
    inputs = replace(inputs, template_schedule=_schedule(requested.meal_id))

    result = plan_week(
        inputs, (requested_food, excluded_food, safe_food), (requested, excluded, safe)
    )

    assert result.outcome.value == "success"
    assert all(meal.template_id == safe.meal_id for day in result.days for meal in day.meals)
    assert all(
        food.slug != "peanut" for day in result.days for meal in day.meals for food in meal.foods
    )


def test_vegan_profile_does_not_receive_animal_product_substitute() -> None:
    animal = _food("milk", dietary_patterns=("omnivore", "vegetarian"))
    vegan = _food("oats", dietary_patterns=("vegan",))
    requested = _template("animal", "lunch", animal.food_id)
    replacement = _template("vegan", "lunch", vegan.food_id)
    inputs = _input(dietary_pattern="vegan")
    inputs = replace(inputs, template_schedule=_schedule(requested.meal_id))

    result = plan_week(inputs, (animal, vegan), (requested, replacement))

    assert result.outcome.value == "success"
    assert all(meal.template_id == replacement.meal_id for day in result.days for meal in day.meals)


def test_prepared_recipe_with_missing_required_ingredient_is_not_a_substitute() -> None:
    safe_food = _food("safe")
    missing_id = "missing-required-food"
    recipe_template = PlannerMealTemplate(
        meal_id="incomplete-recipe",
        name_fa="incomplete-recipe",
        name_en="incomplete-recipe",
        category="lunch",
        items=(),
        prepared_recipe=PlannerPreparedRecipe(
            revision_id="recipe-revision",
            name_fa="recipe",
            name_en="recipe",
            verification_status="verified",
            definition=PreparedRecipeDefinition(
                calculation_version="prepared-recipe-v1",
                ingredients=(
                    PreparedRecipeIngredient(
                        food_id=missing_id,
                        reference_grams=Decimal("100"),
                        min_grams=Decimal("50"),
                        max_grams=Decimal("150"),
                        is_required=True,
                    ),
                ),
                ratios=(),
                cooked_yield=PreparedRecipeYield(
                    method="proportional_reference_batch",
                    reference_input_grams=Decimal("100"),
                    final_cooked_yield_grams=Decimal("100"),
                ),
            ),
        ),
    )
    replacement = _template("safe-lunch", "lunch", safe_food.food_id)
    inputs = _input()
    inputs = replace(inputs, template_schedule=_schedule(recipe_template.meal_id))

    result = plan_week(inputs, (safe_food,), (recipe_template, replacement))

    assert result.outcome.value == "success"
    assert all(meal.template_id == replacement.meal_id for day in result.days for meal in day.meals)


def test_invalid_portion_bounds_are_not_eligible_substitutes() -> None:
    food = _food("food")
    invalid = _template(
        "invalid-lunch",
        "lunch",
        food.food_id,
        reference="100",
        minimum="250",
        maximum="300",
    )

    assert _eligible_templates(_input(), (food,), (invalid,)) == ()


def test_invalid_prepared_recipe_is_not_an_eligible_substitute() -> None:
    food = _food("food")
    invalid = PlannerMealTemplate(
        meal_id="invalid-recipe",
        name_fa="invalid-recipe",
        name_en="invalid-recipe",
        category="lunch",
        items=(),
        prepared_recipe=PlannerPreparedRecipe(
            revision_id="invalid-recipe-revision",
            name_fa="invalid-recipe",
            name_en="invalid-recipe",
            verification_status="verified",
            definition=PreparedRecipeDefinition(
                calculation_version="prepared-recipe-v1",
                ingredients=(
                    PreparedRecipeIngredient(
                        food_id=food.food_id,
                        reference_grams=Decimal("0"),
                        min_grams=Decimal("0"),
                        max_grams=Decimal("100"),
                        is_required=True,
                    ),
                ),
                ratios=(),
                cooked_yield=PreparedRecipeYield(
                    method="proportional_reference_batch",
                    reference_input_grams=Decimal("100"),
                    final_cooked_yield_grams=Decimal("100"),
                ),
            ),
        ),
    )

    assert _eligible_templates(_input(), (food,), (invalid,)) == ()


def test_unverified_template_never_enters_the_plan() -> None:
    food = _food("food")
    unverified = _template("draft-lunch", "lunch", food.food_id, verification_status="draft")
    verified = _template("verified-lunch", "lunch", food.food_id)
    inputs = _input()
    inputs = replace(inputs, template_schedule=_schedule(unverified.meal_id))

    result = plan_week(inputs, (food,), (unverified, verified))

    assert result.outcome.value == "success"
    assert all(meal.template_id == verified.meal_id for day in result.days for meal in day.meals)


def test_next_ranked_substitute_is_tried_when_first_variant_cannot_meet_target() -> None:
    low_capacity_food = _food("low-capacity", kcal="180")
    viable_food = _food("viable", kcal="220")
    requested = _template("missing", "lunch", "missing-food")
    low_capacity = _template(
        "lunch-a",
        "lunch",
        low_capacity_food.food_id,
        maximum="50",
    )
    viable = _template("lunch-b", "lunch", viable_food.food_id)
    inputs = _input()
    inputs = replace(inputs, template_schedule=_schedule(requested.meal_id))

    result = plan_week(
        inputs,
        (low_capacity_food, viable_food),
        (requested, low_capacity, viable),
    )

    assert result.outcome.value == "success"
    assert all(meal.template_id == viable.meal_id for day in result.days for meal in day.meals)
    assert all(
        action.replacement_template_id == viable.meal_id for action in result.substitution_actions
    )


def test_no_compatible_substitute_returns_a_precise_failure() -> None:
    requested_food = _food("requested")
    dinner_food = _food("dinner")
    requested = _template("missing-lunch", "lunch", requested_food.food_id)
    dinner = _template("dinner", "dinner", dinner_food.food_id)
    inputs = _input()
    schedule = tuple(
        (("main_meal", requested.meal_id, "lunch"), ("main_meal", dinner.meal_id, "dinner"))
        for _ in range(7)
    )
    inputs = replace(inputs, template_schedule=schedule)

    result = plan_week(inputs, (dinner_food,), (requested, dinner))

    assert result.outcome.value == "infeasible"
    assert result.reason_codes == ("NO_COMPATIBLE_TEMPLATE_SUBSTITUTE",)
    assert result.substitution_diagnostics == (
        {
            "day_index": "0",
            "role": "main_meal",
            "slot_index": "0",
            "slot_category": "lunch",
            "dietary_pattern": "omnivore",
            "excluded_terms": "",
            "requested_template_id": requested.meal_id,
            "candidate_template_id": dinner.meal_id,
            "eligible_alternative_count": "0",
            "reason_code": "SLOT_CATEGORY_MISMATCH+REPETITION_LIMIT_EXCEEDED",
        },
    )


def test_candidate_quality_counts_substitutions_and_uses_variant_identity() -> None:
    proposal = ProgramCandidate(
        program=NutritionProgram(
            code="P01",
            slug="p01",
            diet_style=NutritionDietStyle.BALANCED_IRANIAN,
        ),
        preferred_style=True,
        preconstruction_rank=0,
    )
    result = PlannerResult(
        outcome=GenerationOutcome.SUCCESS,
        reason_codes=("SAFE_FEASIBLE_DRAFT_GENERATED",),
        substitution_actions=(
            SubstitutionAction(
                day_index=0,
                role="main_meal",
                slot_index=0,
                requested_template_id="requested",
                replacement_template_id="replacement",
                reason_code="SCHEDULED_TEMPLATE_UNAVAILABLE",
            ),
        ),
    )

    evaluation = evaluate_candidate(
        proposal,
        result,
        weekly_budget_irr=Decimal("100000"),
    )

    assert evaluation.quality is not None
    assert evaluation.quality.substitution_burden == 1
    assert evaluation.stable_variant_key == ("00:main_meal:00:replacement",)


def test_substitution_for_allergy_produces_allergy_reason_code() -> None:
    fish_food = _food("fish", allergen_tags=("fish",), allergen_metadata_verified=True)
    safe_chicken = _food("chicken", allergen_tags=(), allergen_metadata_verified=True)
    fish_meal = _template("fish-meal", "lunch", fish_food.food_id)
    chicken_meal = _template("chicken-meal", "lunch", safe_chicken.food_id)

    constraints = normalize_food_constraints([{"kind": "allergy", "term": "ماهی"}])
    inputs = _input()
    schedule = tuple((("main_meal", fish_meal.meal_id, "lunch"),) for _ in range(7))
    inputs = replace(inputs, template_schedule=schedule, food_constraints=tuple(constraints))

    result = plan_week(inputs, (fish_food, safe_chicken), (fish_meal, chicken_meal))

    assert result.outcome == GenerationOutcome.SUCCESS
    assert len(result.substitution_actions) == 7
    for action in result.substitution_actions:
        assert action.requested_template_id == "fish-meal"
        assert action.replacement_template_id == "chicken-meal"
        assert action.reason_code == "MEAL_SUBSTITUTED_FOR_ALLERGY"

    for day in result.days:
        for meal in day.meals:
            for food in meal.foods:
                assert food.slug != "fish"


def test_substitution_for_intolerance_produces_intolerance_reason_code() -> None:
    main_food = _food("rice", allergen_tags=(), allergen_metadata_verified=True)
    main_meal = _template("rice-meal", "lunch", main_food.food_id)
    dairy_food = _food("milk", allergen_tags=("milk",), allergen_metadata_verified=True)
    oat_food = _food("oat-milk", allergen_tags=(), allergen_metadata_verified=True)
    dairy_snack = _template("dairy-snack", "snack", dairy_food.food_id)
    oat_snack = _template("oat-snack", "snack", oat_food.food_id)

    constraints = normalize_food_constraints([{"kind": "intolerance", "term": "لاکتوز"}])
    inputs = _input()
    schedule = tuple((("snack", dairy_snack.meal_id, "snack"),) for _ in range(7))
    inputs = replace(
        inputs,
        template_schedule=schedule,
        food_constraints=tuple(constraints),
        snacks_per_day=1,
    )

    result = plan_week(
        inputs,
        (main_food, dairy_food, oat_food),
        (main_meal, dairy_snack, oat_snack),
    )

    assert result.outcome == GenerationOutcome.SUCCESS
    assert len(result.substitution_actions) == 7
    for action in result.substitution_actions:
        assert action.requested_template_id == "dairy-snack"
        assert action.replacement_template_id == "oat-snack"
        assert action.reason_code == "MEAL_SUBSTITUTED_FOR_INTOLERANCE"


def test_substitution_for_hard_exclusion_produces_exclusion_reason_code() -> None:
    beef_food = _food("beef", allergen_tags=(), allergen_metadata_verified=True)
    chicken_food = _food("chicken", allergen_tags=(), allergen_metadata_verified=True)
    beef_meal = _template("beef-meal", "lunch", beef_food.food_id)
    chicken_meal = _template("chicken-meal", "lunch", chicken_food.food_id)

    constraints = normalize_food_constraints([{"kind": "never_suggest", "term": "beef"}])
    inputs = _input()
    schedule = tuple((("main_meal", beef_meal.meal_id, "lunch"),) for _ in range(7))
    inputs = replace(inputs, template_schedule=schedule, food_constraints=tuple(constraints))

    result = plan_week(inputs, (beef_food, chicken_food), (beef_meal, chicken_meal))

    assert result.outcome == GenerationOutcome.SUCCESS
    assert len(result.substitution_actions) == 7
    for action in result.substitution_actions:
        assert action.reason_code == "MEAL_SUBSTITUTED_FOR_HARD_EXCLUSION"
        assert action.replacement_template_id == "chicken-meal"


def test_program_with_incompatible_meal_survives_when_substitute_available() -> None:
    main_food = _food("rice", allergen_tags=(), allergen_metadata_verified=True)
    main_meal = _template("rice-meal", "lunch", main_food.food_id)
    bad_food = _food("peanuts", allergen_tags=("peanut",), allergen_metadata_verified=True)
    good_food = _food("almonds", allergen_tags=("tree_nut",), allergen_metadata_verified=True)
    bad_snack = _template("peanut-snack", "snack", bad_food.food_id)
    good_snack = _template("almond-snack", "snack", good_food.food_id)

    constraints = normalize_food_constraints([{"kind": "allergy", "term": "peanut"}])
    inputs = _input()
    schedule = tuple((("snack", bad_snack.meal_id, "snack"),) for _ in range(7))
    inputs = replace(
        inputs,
        template_schedule=schedule,
        food_constraints=tuple(constraints),
        snacks_per_day=1,
    )

    result = plan_week(
        inputs,
        (main_food, bad_food, good_food),
        (main_meal, bad_snack, good_snack),
    )

    assert result.outcome == GenerationOutcome.SUCCESS
    assert result.days[0].meals[0].template_id == "almond-snack"
