"""Generic calculation and validation for immutable Prepared Recipe revisions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

HUNDRED = Decimal("100")
ZERO = Decimal("0")
CALCULATION_VERSION = "prepared-recipe-v1"
YIELD_METHOD = "proportional_reference_batch"


@dataclass(frozen=True)
class PreparedRecipeIngredient:
    food_id: UUID
    reference_grams: Decimal
    min_grams: Decimal
    max_grams: Decimal
    is_required: bool


@dataclass(frozen=True)
class PreparedRecipeRatio:
    numerator_food_id: UUID
    denominator_food_id: UUID
    min_ratio: Decimal
    max_ratio: Decimal


@dataclass(frozen=True)
class PreparedRecipeYield:
    method: str
    reference_input_grams: Decimal
    final_cooked_yield_grams: Decimal


@dataclass(frozen=True)
class PreparedRecipeDefinition:
    calculation_version: str
    ingredients: tuple[PreparedRecipeIngredient, ...]
    ratios: tuple[PreparedRecipeRatio, ...]
    cooked_yield: PreparedRecipeYield


@dataclass(frozen=True)
class PreparedRecipeFood:
    food_id: UUID
    nutrients_per_100g: dict[str, Decimal]
    price_irr_per_gram: Decimal
    price_reference_id: str


@dataclass(frozen=True)
class PreparedRecipeCalculation:
    calculation_version: str
    selected_ingredient_grams: tuple[tuple[UUID, Decimal], ...]
    final_cooked_yield_grams: Decimal
    total_nutrients: tuple[tuple[str, Decimal], ...]
    nutrients_per_100g: dict[str, Decimal]
    total_cost_irr: Decimal
    cost_irr_per_100g: Decimal
    price_reference_ids: tuple[str, ...]


def validate_prepared_recipe(
    definition: PreparedRecipeDefinition,
    available_food_ids: set[UUID],
) -> None:
    if definition.calculation_version != CALCULATION_VERSION:
        raise ValueError("Unsupported Prepared Recipe calculation version")
    if not definition.ingredients:
        raise ValueError("Prepared Recipe requires at least one ingredient")
    ingredient_by_id = {ingredient.food_id: ingredient for ingredient in definition.ingredients}
    if len(ingredient_by_id) != len(definition.ingredients):
        raise ValueError("Prepared Recipe foods must be unique")
    missing = set(ingredient_by_id) - available_food_ids
    if missing:
        raise ValueError("Prepared Recipe ingredient does not exist in Food Catalogue")
    for ingredient in definition.ingredients:
        if (
            ingredient.is_required
            and min(
                ingredient.min_grams,
                ingredient.reference_grams,
                ingredient.max_grams,
            )
            <= ZERO
        ):
            raise ValueError("Prepared Recipe required quantities must be positive")
        if ingredient.min_grams < ZERO or not (
            ingredient.min_grams <= ingredient.reference_grams <= ingredient.max_grams
        ):
            raise ValueError("Prepared Recipe ingredients must satisfy min <= reference <= max")

    cooked_yield = definition.cooked_yield
    if cooked_yield.method != YIELD_METHOD:
        raise ValueError("Unsupported Prepared Recipe cooked yield method")
    if cooked_yield.reference_input_grams <= ZERO or cooked_yield.final_cooked_yield_grams <= ZERO:
        raise ValueError("Prepared Recipe cooked yield is required")
    reference_total = sum(
        (ingredient.reference_grams for ingredient in definition.ingredients), ZERO
    )
    if reference_total != cooked_yield.reference_input_grams:
        raise ValueError("Cooked yield reference input must equal ingredient reference grams")

    seen_ratios: set[tuple[UUID, UUID]] = set()
    for ratio in definition.ratios:
        pair = (ratio.numerator_food_id, ratio.denominator_food_id)
        if pair in seen_ratios:
            raise ValueError("Prepared Recipe ratio constraints must be unique")
        seen_ratios.add(pair)
        if ratio.numerator_food_id == ratio.denominator_food_id:
            raise ValueError("Prepared Recipe ratio cannot reference the same ingredient")
        numerator = ingredient_by_id.get(ratio.numerator_food_id)
        denominator = ingredient_by_id.get(ratio.denominator_food_id)
        if numerator is None or denominator is None:
            raise ValueError("Prepared Recipe ratio ingredient does not exist")
        if ratio.min_ratio <= ZERO or ratio.min_ratio > ratio.max_ratio:
            raise ValueError("Prepared Recipe ratio bounds are invalid")
        if denominator.max_grams <= ZERO:
            raise ValueError("Prepared Recipe ratio denominator must be positive")
        possible_min = numerator.min_grams / denominator.max_grams
        if denominator.min_grams <= ZERO:
            possible_max = Decimal("Infinity")
        else:
            possible_max = numerator.max_grams / denominator.min_grams
        if ratio.max_ratio < possible_min or ratio.min_ratio > possible_max:
            raise ValueError("Prepared Recipe has an impossible ratio constraint")
        _validate_ratio_value(
            ratio,
            numerator.reference_grams,
            denominator.reference_grams,
            message="Prepared Recipe reference grams violate a ratio constraint",
        )


def calculate_prepared_recipe(
    definition: PreparedRecipeDefinition,
    foods: dict[UUID, PreparedRecipeFood],
    *,
    quantities: dict[UUID, Decimal] | None = None,
) -> PreparedRecipeCalculation:
    validate_prepared_recipe(definition, set(foods))
    requested = quantities or {
        ingredient.food_id: ingredient.reference_grams for ingredient in definition.ingredients
    }
    if set(requested) != {ingredient.food_id for ingredient in definition.ingredients}:
        raise ValueError("Prepared Recipe quantities must include every recipe ingredient")
    ingredient_by_id = {ingredient.food_id: ingredient for ingredient in definition.ingredients}
    for food_id, grams in requested.items():
        ingredient = ingredient_by_id[food_id]
        if grams < ingredient.min_grams or grams > ingredient.max_grams:
            raise ValueError("Prepared Recipe quantity is outside ingredient bounds")
        if ingredient.is_required and grams <= ZERO:
            raise ValueError("Prepared Recipe required quantities must be positive")
    for ratio in definition.ratios:
        _validate_ratio_value(
            ratio,
            requested[ratio.numerator_food_id],
            requested[ratio.denominator_food_id],
            message="Prepared Recipe quantities violate a ratio constraint",
        )

    nutrient_totals: dict[str, Decimal] = {}
    total_cost = ZERO
    for ingredient in definition.ingredients:
        grams = requested[ingredient.food_id]
        food = foods[ingredient.food_id]
        for code, value in food.nutrients_per_100g.items():
            nutrient_totals[code] = nutrient_totals.get(code, ZERO) + value * grams / HUNDRED
        total_cost += food.price_irr_per_gram * grams

    selected_input = sum(requested.values(), ZERO)
    cooked_yield = (
        definition.cooked_yield.final_cooked_yield_grams
        * selected_input
        / definition.cooked_yield.reference_input_grams
    )
    return PreparedRecipeCalculation(
        calculation_version=definition.calculation_version,
        selected_ingredient_grams=tuple(sorted(requested.items(), key=lambda row: str(row[0]))),
        final_cooked_yield_grams=cooked_yield,
        total_nutrients=tuple(sorted(nutrient_totals.items())),
        nutrients_per_100g={
            code: value * HUNDRED / cooked_yield for code, value in sorted(nutrient_totals.items())
        },
        total_cost_irr=total_cost,
        cost_irr_per_100g=total_cost * HUNDRED / cooked_yield,
        price_reference_ids=tuple(
            foods[ingredient.food_id].price_reference_id for ingredient in definition.ingredients
        ),
    )


def _validate_ratio_value(
    ratio: PreparedRecipeRatio,
    numerator_grams: Decimal,
    denominator_grams: Decimal,
    *,
    message: str,
) -> None:
    if denominator_grams <= ZERO:
        raise ValueError(message)
    selected_ratio = numerator_grams / denominator_grams
    if selected_ratio < ratio.min_ratio or selected_ratio > ratio.max_ratio:
        raise ValueError(message)
