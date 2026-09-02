"""Deterministic price-to-mass conversions used at the Planner boundary."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal, cast

PriceCanonicalUnit = Literal["TOMAN_PER_KG", "TOMAN_PER_LITER", "TOMAN_PER_UNIT"]

PRICE_MASS_CONVERSION_VERSION: Final = "price-mass-equivalent-v1"
PRICE_MASS_CONVERSION_SOURCE_NAME: Final = "Fitsho approved price-mass equivalent baseline"
PRICE_MASS_CONVERSION_SOURCE_REFERENCE: Final = (
    "approved-task-baseline:price-mass-equivalent-v1"
)
KG_CONVERSION_METHOD: Final = "canonical_kg"
NON_KG_CONVERSION_METHOD: Final = "approved_pricing_mass_equivalent"
VALID_PRICE_CANONICAL_UNITS: Final = frozenset(
    {"TOMAN_PER_KG", "TOMAN_PER_LITER", "TOMAN_PER_UNIT"}
)
ZERO = Decimal("0")
TOMAN_TO_IRR = Decimal("10")
KG_GRAMS_PER_PRICE_UNIT = Decimal("1000")


@dataclass(frozen=True)
class PriceMassBasis:
    slug: str
    canonical_unit: PriceCanonicalUnit
    grams_per_price_unit: Decimal
    method: str
    source_name: str
    source_reference: str


@dataclass(frozen=True)
class PricePerGramConversion:
    food_slug: str
    price_irr_per_gram: Decimal
    original_canonical_unit: PriceCanonicalUnit
    grams_per_price_unit: Decimal
    conversion_method: str
    conversion_version: str
    source_name: str
    source_reference: str


class PriceMassConversionError(ValueError):
    """Base error for a missing or incompatible deterministic mass conversion."""

    code = "PRICE_MASS_CONVERSION_ERROR"

    def __init__(self, *, food_slug: str, canonical_unit: str, detail: str) -> None:
        self.food_slug = food_slug
        self.canonical_unit = canonical_unit
        super().__init__(f"{self.code}: {food_slug} ({canonical_unit}); {detail}")


class PriceMassConversionMissingError(PriceMassConversionError):
    code = "PRICE_MASS_CONVERSION_MISSING"


class PriceMassConversionUnitMismatchError(PriceMassConversionError):
    code = "PRICE_MASS_CONVERSION_UNIT_MISMATCH"


class PriceMassConversionUnsupportedUnitError(PriceMassConversionError):
    code = "PRICE_MASS_CONVERSION_UNSUPPORTED_UNIT"


PRICE_MASS_BASES: Final[dict[str, PriceMassBasis]] = {
    "egg": PriceMassBasis(
        slug="egg",
        canonical_unit="TOMAN_PER_UNIT",
        grams_per_price_unit=Decimal("50"),
        method=NON_KG_CONVERSION_METHOD,
        source_name=PRICE_MASS_CONVERSION_SOURCE_NAME,
        source_reference=PRICE_MASS_CONVERSION_SOURCE_REFERENCE,
    ),
    "sangak-bread": PriceMassBasis(
        slug="sangak-bread",
        canonical_unit="TOMAN_PER_UNIT",
        grams_per_price_unit=Decimal("600"),
        method=NON_KG_CONVERSION_METHOD,
        source_name=PRICE_MASS_CONVERSION_SOURCE_NAME,
        source_reference=PRICE_MASS_CONVERSION_SOURCE_REFERENCE,
    ),
    "barbari-bread": PriceMassBasis(
        slug="barbari-bread",
        canonical_unit="TOMAN_PER_UNIT",
        grams_per_price_unit=Decimal("550"),
        method=NON_KG_CONVERSION_METHOD,
        source_name=PRICE_MASS_CONVERSION_SOURCE_NAME,
        source_reference=PRICE_MASS_CONVERSION_SOURCE_REFERENCE,
    ),
    "lavash-bread": PriceMassBasis(
        slug="lavash-bread",
        canonical_unit="TOMAN_PER_UNIT",
        grams_per_price_unit=Decimal("130"),
        method=NON_KG_CONVERSION_METHOD,
        source_name=PRICE_MASS_CONVERSION_SOURCE_NAME,
        source_reference=PRICE_MASS_CONVERSION_SOURCE_REFERENCE,
    ),
    "taftoon-bread": PriceMassBasis(
        slug="taftoon-bread",
        canonical_unit="TOMAN_PER_UNIT",
        grams_per_price_unit=Decimal("320"),
        method=NON_KG_CONVERSION_METHOD,
        source_name=PRICE_MASS_CONVERSION_SOURCE_NAME,
        source_reference=PRICE_MASS_CONVERSION_SOURCE_REFERENCE,
    ),
    "milk": PriceMassBasis(
        slug="milk",
        canonical_unit="TOMAN_PER_LITER",
        grams_per_price_unit=Decimal("1030"),
        method=NON_KG_CONVERSION_METHOD,
        source_name=PRICE_MASS_CONVERSION_SOURCE_NAME,
        source_reference=PRICE_MASS_CONVERSION_SOURCE_REFERENCE,
    ),
    "olive-oil": PriceMassBasis(
        slug="olive-oil",
        canonical_unit="TOMAN_PER_LITER",
        grams_per_price_unit=Decimal("913"),
        method=NON_KG_CONVERSION_METHOD,
        source_name=PRICE_MASS_CONVERSION_SOURCE_NAME,
        source_reference=PRICE_MASS_CONVERSION_SOURCE_REFERENCE,
    ),
    "vegetable-oil": PriceMassBasis(
        slug="vegetable-oil",
        canonical_unit="TOMAN_PER_LITER",
        grams_per_price_unit=Decimal("920"),
        method=NON_KG_CONVERSION_METHOD,
        source_name=PRICE_MASS_CONVERSION_SOURCE_NAME,
        source_reference=PRICE_MASS_CONVERSION_SOURCE_REFERENCE,
    ),
}


def planner_price_irr_per_gram(
    *,
    food_slug: str,
    reference_price_toman: Decimal,
    canonical_unit: str,
) -> PricePerGramConversion:
    """Convert an effective Toman price into the Planner's IRR-per-gram value."""

    if not isinstance(reference_price_toman, Decimal):
        raise TypeError("reference_price_toman must be a Decimal")
    if not reference_price_toman.is_finite() or reference_price_toman <= ZERO:
        raise ValueError("reference_price_toman must be finite and positive")
    if canonical_unit not in VALID_PRICE_CANONICAL_UNITS:
        raise PriceMassConversionUnsupportedUnitError(
            food_slug=food_slug,
            canonical_unit=canonical_unit,
            detail="canonical unit is not supported",
        )
    typed_unit = cast(PriceCanonicalUnit, canonical_unit)
    if typed_unit == "TOMAN_PER_KG":
        basis = PriceMassBasis(
            slug=food_slug,
            canonical_unit=typed_unit,
            grams_per_price_unit=KG_GRAMS_PER_PRICE_UNIT,
            method=KG_CONVERSION_METHOD,
            source_name="Canonical TOMAN_PER_KG pricing unit",
            source_reference="canonical-unit:TOMAN_PER_KG",
        )
    else:
        basis = PRICE_MASS_BASES.get(food_slug)
        if basis is None:
            raise PriceMassConversionMissingError(
                food_slug=food_slug,
                canonical_unit=canonical_unit,
                detail="no approved grams_per_price_unit metadata exists",
            )
        if basis.canonical_unit != typed_unit:
            raise PriceMassConversionUnitMismatchError(
                food_slug=food_slug,
                canonical_unit=canonical_unit,
                detail=f"metadata is for {basis.canonical_unit}",
            )

    price_irr_per_gram = (
        reference_price_toman * TOMAN_TO_IRR / basis.grams_per_price_unit
    )
    return PricePerGramConversion(
        food_slug=food_slug,
        price_irr_per_gram=price_irr_per_gram,
        original_canonical_unit=basis.canonical_unit,
        grams_per_price_unit=basis.grams_per_price_unit,
        conversion_method=basis.method,
        conversion_version=PRICE_MASS_CONVERSION_VERSION,
        source_name=basis.source_name,
        source_reference=basis.source_reference,
    )
