from decimal import Decimal
from uuid import UUID

import pytest

from app.nutrition.prepared_recipe import (
    PreparedRecipeDefinition,
    PreparedRecipeFood,
    PreparedRecipeIngredient,
    PreparedRecipeRatio,
    PreparedRecipeYield,
    calculate_prepared_recipe,
    validate_prepared_recipe,
)


def _definition() -> tuple[PreparedRecipeDefinition, PreparedRecipeFood, PreparedRecipeFood]:
    beef_id = UUID(int=1)
    pea_id = UUID(int=2)
    beef = PreparedRecipeFood(
        food_id=beef_id,
        nutrients_per_100g={
            "energy_kcal": Decimal("200"),
            "protein_g": Decimal("20"),
            "iron_mg": Decimal("2"),
        },
        price_irr_per_gram=Decimal("1000"),
        price_reference_id="beef-price-v1",
    )
    peas = PreparedRecipeFood(
        food_id=pea_id,
        nutrients_per_100g={
            "energy_kcal": Decimal("360"),
            "protein_g": Decimal("24"),
            "carbohydrate_g": Decimal("60"),
            "iron_mg": Decimal("5"),
        },
        price_irr_per_gram=Decimal("200"),
        price_reference_id="pea-price-v1",
    )
    definition = PreparedRecipeDefinition(
        calculation_version="prepared-recipe-v1",
        ingredients=(
            PreparedRecipeIngredient(
                food_id=beef_id,
                reference_grams=Decimal("100"),
                min_grams=Decimal("80"),
                max_grams=Decimal("120"),
                is_required=True,
            ),
            PreparedRecipeIngredient(
                food_id=pea_id,
                reference_grams=Decimal("50"),
                min_grams=Decimal("40"),
                max_grams=Decimal("60"),
                is_required=True,
            ),
        ),
        ratios=(
            PreparedRecipeRatio(
                numerator_food_id=beef_id,
                denominator_food_id=pea_id,
                min_ratio=Decimal("1.5"),
                max_ratio=Decimal("2.5"),
            ),
        ),
        cooked_yield=PreparedRecipeYield(
            method="proportional_reference_batch",
            reference_input_grams=Decimal("150"),
            final_cooked_yield_grams=Decimal("300"),
        ),
    )
    return definition, beef, peas


def test_calculates_all_nutrients_and_cost_per_100g_of_cooked_food() -> None:
    definition, beef, peas = _definition()

    result = calculate_prepared_recipe(definition, {beef.food_id: beef, peas.food_id: peas})

    assert result.final_cooked_yield_grams == Decimal("300")
    assert result.nutrients_per_100g == {
        "carbohydrate_g": Decimal("10"),
        "energy_kcal": Decimal("126.6666666666666666666666667"),
        "iron_mg": Decimal("1.5"),
        "protein_g": Decimal("10.66666666666666666666666667"),
    }
    assert result.cost_irr_per_100g == Decimal("36666.66666666666666666666667")
    assert result.price_reference_ids == ("beef-price-v1", "pea-price-v1")


def test_applies_cooked_yield_to_a_bounded_recipe_variant_deterministically() -> None:
    definition, beef, peas = _definition()
    quantities = {beef.food_id: Decimal("120"), peas.food_id: Decimal("50")}

    first = calculate_prepared_recipe(
        definition,
        {beef.food_id: beef, peas.food_id: peas},
        quantities=quantities,
    )
    second = calculate_prepared_recipe(
        definition,
        {peas.food_id: peas, beef.food_id: beef},
        quantities=quantities,
    )

    assert first == second
    assert first.final_cooked_yield_grams == Decimal("340")
    assert first.selected_ingredient_grams == tuple(
        sorted(quantities.items(), key=lambda row: str(row[0]))
    )


def test_dynamic_cost_uses_the_current_effective_ingredient_prices() -> None:
    definition, beef, peas = _definition()
    initial = calculate_prepared_recipe(definition, {beef.food_id: beef, peas.food_id: peas})
    repriced_beef = PreparedRecipeFood(
        food_id=beef.food_id,
        nutrients_per_100g=beef.nutrients_per_100g,
        price_irr_per_gram=Decimal("1500"),
        price_reference_id="beef-price-v2",
    )

    updated = calculate_prepared_recipe(
        definition,
        {repriced_beef.food_id: repriced_beef, peas.food_id: peas},
    )

    assert updated.cost_irr_per_100g > initial.cost_irr_per_100g
    assert updated.price_reference_ids == ("beef-price-v2", "pea-price-v1")


@pytest.mark.parametrize(
    ("ingredient_patch", "error"),
    [
        ({"min_grams": Decimal("101")}, "min <= reference <= max"),
        ({"max_grams": Decimal("99")}, "min <= reference <= max"),
        ({"reference_grams": Decimal("0")}, "required quantities must be positive"),
    ],
)
def test_rejects_invalid_ingredient_bounds(
    ingredient_patch: dict[str, Decimal], error: str
) -> None:
    definition, beef, _ = _definition()
    ingredient = definition.ingredients[0]
    values = {
        "food_id": ingredient.food_id,
        "reference_grams": ingredient.reference_grams,
        "min_grams": ingredient.min_grams,
        "max_grams": ingredient.max_grams,
        "is_required": ingredient.is_required,
        **ingredient_patch,
    }
    invalid = PreparedRecipeDefinition(
        calculation_version=definition.calculation_version,
        ingredients=(PreparedRecipeIngredient(**values), definition.ingredients[1]),
        ratios=definition.ratios,
        cooked_yield=definition.cooked_yield,
    )

    with pytest.raises(ValueError, match=error):
        validate_prepared_recipe(invalid, {beef.food_id, definition.ingredients[1].food_id})


def test_rejects_missing_food_and_impossible_ratio_constraints() -> None:
    definition, beef, peas = _definition()
    impossible = PreparedRecipeDefinition(
        calculation_version=definition.calculation_version,
        ingredients=(
            PreparedRecipeIngredient(
                food_id=beef.food_id,
                reference_grams=Decimal("90"),
                min_grams=Decimal("80"),
                max_grams=Decimal("100"),
                is_required=True,
            ),
            PreparedRecipeIngredient(
                food_id=peas.food_id,
                reference_grams=Decimal("65"),
                min_grams=Decimal("60"),
                max_grams=Decimal("70"),
                is_required=True,
            ),
        ),
        ratios=(
            PreparedRecipeRatio(
                numerator_food_id=beef.food_id,
                denominator_food_id=peas.food_id,
                min_ratio=Decimal("2"),
                max_ratio=Decimal("3"),
            ),
        ),
        cooked_yield=PreparedRecipeYield(
            method="proportional_reference_batch",
            reference_input_grams=Decimal("155"),
            final_cooked_yield_grams=Decimal("300"),
        ),
    )

    with pytest.raises(ValueError, match="does not exist in Food Catalogue"):
        validate_prepared_recipe(definition, {beef.food_id})
    with pytest.raises(ValueError, match="impossible ratio"):
        validate_prepared_recipe(impossible, {beef.food_id, peas.food_id})


def test_future_recipe_uses_the_same_generic_calculator() -> None:
    definition, beef, peas = _definition()
    future_recipe = PreparedRecipeDefinition(
        calculation_version=definition.calculation_version,
        ingredients=tuple(reversed(definition.ingredients)),
        ratios=tuple(
            PreparedRecipeRatio(
                numerator_food_id=ratio.denominator_food_id,
                denominator_food_id=ratio.numerator_food_id,
                min_ratio=Decimal("1") / ratio.max_ratio,
                max_ratio=Decimal("1") / ratio.min_ratio,
            )
            for ratio in definition.ratios
        ),
        cooked_yield=definition.cooked_yield,
    )

    result = calculate_prepared_recipe(future_recipe, {beef.food_id: beef, peas.food_id: peas})

    assert result.nutrients_per_100g["protein_g"] > 0
