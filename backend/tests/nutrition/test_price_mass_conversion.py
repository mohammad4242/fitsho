from decimal import Decimal

import pytest


def test_converts_toman_per_kg_to_irr_per_gram() -> None:
    from app.nutrition.price_mass_conversion import planner_price_irr_per_gram

    conversion = planner_price_irr_per_gram(
        food_slug="basmati-rice",
        reference_price_toman=Decimal("350000"),
        canonical_unit="TOMAN_PER_KG",
    )

    assert conversion.price_irr_per_gram == Decimal("3500")
    assert conversion.original_canonical_unit == "TOMAN_PER_KG"
    assert conversion.grams_per_price_unit == Decimal("1000")


def test_converts_egg_unit_price_using_its_pricing_mass_equivalent() -> None:
    from app.nutrition.price_mass_conversion import planner_price_irr_per_gram

    conversion = planner_price_irr_per_gram(
        food_slug="egg",
        reference_price_toman=Decimal("21000"),
        canonical_unit="TOMAN_PER_UNIT",
    )

    assert conversion.price_irr_per_gram == Decimal("4200")
    assert conversion.grams_per_price_unit == Decimal("50")
    assert conversion.conversion_version == "price-mass-equivalent-v1"


def test_converts_pineapple_unit_price_using_its_pricing_mass_equivalent() -> None:
    from app.nutrition.price_mass_conversion import planner_price_irr_per_gram

    conversion = planner_price_irr_per_gram(
        food_slug="pineapple",
        reference_price_toman=Decimal("307000"),
        canonical_unit="TOMAN_PER_UNIT",
    )

    assert conversion.price_irr_per_gram == Decimal("307000") * Decimal("10") / Decimal("905")
    assert conversion.grams_per_price_unit == Decimal("905")
    assert conversion.source_name == "USDA FoodData Central SR Legacy"
    assert conversion.source_reference == "USDA FDC SR Legacy food 169124, portion fruit"


@pytest.mark.parametrize(
    ("slug", "price", "unit", "grams"),
    [
        ("sangak-bread", "15500", "TOMAN_PER_UNIT", "600"),
        ("barbari-bread", "10000", "TOMAN_PER_UNIT", "550"),
        ("lavash-bread", "2700", "TOMAN_PER_UNIT", "130"),
        ("taftoon-bread", "4500", "TOMAN_PER_UNIT", "320"),
        ("milk", "120000", "TOMAN_PER_LITER", "1030"),
        ("olive-oil", "1400000", "TOMAN_PER_LITER", "913"),
        ("vegetable-oil", "410000", "TOMAN_PER_LITER", "920"),
    ],
)
def test_converts_non_kg_foods_from_typed_catalogue_baseline(
    slug: str, price: str, unit: str, grams: str
) -> None:
    from app.nutrition.price_mass_conversion import planner_price_irr_per_gram

    conversion = planner_price_irr_per_gram(
        food_slug=slug,
        reference_price_toman=Decimal(price),
        canonical_unit=unit,
    )

    assert conversion.price_irr_per_gram == Decimal(price) * Decimal("10") / Decimal(grams)
    assert conversion.grams_per_price_unit == Decimal(grams)
    assert conversion.original_canonical_unit == unit


def test_missing_non_kg_conversion_is_an_explicit_gap() -> None:
    from app.nutrition.price_mass_conversion import (
        PriceMassConversionMissingError,
        planner_price_irr_per_gram,
    )

    with pytest.raises(PriceMassConversionMissingError) as error:
        planner_price_irr_per_gram(
            food_slug="new-unit-food",
            reference_price_toman=Decimal("10000"),
            canonical_unit="TOMAN_PER_UNIT",
        )

    assert error.value.code == "PRICE_MASS_CONVERSION_MISSING"
    assert error.value.food_slug == "new-unit-food"
    assert error.value.canonical_unit == "TOMAN_PER_UNIT"


def test_conversion_unit_mismatch_fails_safe() -> None:
    from app.nutrition.price_mass_conversion import (
        PriceMassConversionUnitMismatchError,
        planner_price_irr_per_gram,
    )

    with pytest.raises(PriceMassConversionUnitMismatchError) as error:
        planner_price_irr_per_gram(
            food_slug="egg",
            reference_price_toman=Decimal("21000"),
            canonical_unit="TOMAN_PER_LITER",
        )

    assert error.value.code == "PRICE_MASS_CONVERSION_UNIT_MISMATCH"
    assert error.value.food_slug == "egg"
    assert error.value.canonical_unit == "TOMAN_PER_LITER"
