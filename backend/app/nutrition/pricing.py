# ruff: noqa: E501
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from statistics import median
from typing import Protocol


class PriceFreshness(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    ESTIMATED = "estimated"
    UNAVAILABLE = "unavailable"


class PriceReviewReason(StrEnum):
    PRICE_JUMP = "price_jump"
    INSUFFICIENT_SAMPLES = "insufficient_samples"
    SOURCE_DISAGREEMENT = "source_disagreement"
    UNIT_PARSE_ERROR = "unit_parse_error"
    AMBIGUOUS_MATCH = "ambiguous_match"
    OUTLIER = "outlier"
    INVALID_VALUE = "invalid_value"


class PriceValidationError(ValueError):
    pass


class ProviderRateLimitedError(RuntimeError):
    pass


class FoodPriceProvider(Protocol):
    code: str

    async def get_quotes(self, product_ids: list[str]) -> list[PriceObservation]: ...


@dataclass(frozen=True)
class PriceObservation:
    provider_code: str
    provider_product_id: str
    product_title: str
    currency: str
    normal_price: Decimal | None
    promotional_price: Decimal | None
    package_quantity: Decimal
    package_unit: str
    observed_at: datetime
    region: str | None = None


@dataclass(frozen=True)
class NormalizedPriceQuote:
    normalized_normal_price: Decimal | None
    normalized_promotional_price: Decimal | None
    is_promotional: bool
    canonical_unit: str


@dataclass(frozen=True)
class ReferencePriceResult:
    reference_price: Decimal
    accepted_values: tuple[Decimal, ...]
    outliers: tuple[Decimal, ...]


@dataclass(frozen=True)
class ReferencePriceDecision:
    reference_price: Decimal | None
    accepted: bool
    sample_count: int
    review_reasons: tuple[PriceReviewReason, ...]


_UNITS: dict[str, tuple[str, Decimal]] = {
    "g": ("TOMAN_PER_KG", Decimal("1000")),
    "kg": ("TOMAN_PER_KG", Decimal("1")),
    "ml": ("TOMAN_PER_LITER", Decimal("1000")),
    "l": ("TOMAN_PER_LITER", Decimal("1")),
    "unit": ("TOMAN_PER_UNIT", Decimal("1")),
    "item": ("TOMAN_PER_UNIT", Decimal("1")),
}


def normalize_observation(observation: PriceObservation) -> NormalizedPriceQuote:
    if observation.currency not in {"TOMAN", "IRR"}:
        raise PriceValidationError("Unsupported currency")
    if observation.package_quantity <= 0:
        raise PriceValidationError("Invalid package quantity")
    if observation.package_unit not in _UNITS:
        raise PriceValidationError("Unsupported package unit")
    if observation.normal_price is not None and observation.normal_price <= 0:
        raise PriceValidationError("Invalid normal price")
    if observation.promotional_price is not None and observation.promotional_price <= 0:
        raise PriceValidationError("Invalid promotional price")
    if observation.normal_price is None and observation.promotional_price is None:
        raise PriceValidationError("A product must have a price")

    unit, multiplier = _UNITS[observation.package_unit]
    currency_multiplier = Decimal("0.1") if observation.currency == "IRR" else Decimal("1")

    def normalize(value: Decimal | None) -> Decimal | None:
        return None if value is None else value * currency_multiplier * multiplier / observation.package_quantity

    return NormalizedPriceQuote(
        normalized_normal_price=normalize(observation.normal_price),
        normalized_promotional_price=normalize(observation.promotional_price),
        is_promotional=observation.promotional_price is not None,
        canonical_unit=unit,
    )


def classify_freshness(
    observed_at: datetime | None,
    now: datetime,
    fresh_hours: int,
    stale_hours: int,
    estimated_hours: int | None = None,
) -> PriceFreshness:
    if observed_at is None:
        return PriceFreshness.UNAVAILABLE
    age_hours = (now - observed_at).total_seconds() / 3600
    if age_hours <= fresh_hours:
        return PriceFreshness.FRESH
    if age_hours <= stale_hours:
        return PriceFreshness.STALE
    if age_hours <= (estimated_hours or stale_hours * 4):
        return PriceFreshness.ESTIMATED
    return PriceFreshness.UNAVAILABLE


def calculate_reference_price(values: list[Decimal]) -> ReferencePriceResult:
    if not values:
        raise PriceValidationError("No price quotes")
    ordered = sorted(values)
    centre = Decimal(str(median(ordered)))
    # Median-relative filtering remains stable for the small weekly sample sizes we expect.
    accepted = tuple(value for value in ordered if value <= centre * Decimal("1.75"))
    outliers = tuple(value for value in ordered if value not in accepted)
    if not accepted:
        accepted = tuple(ordered)
    return ReferencePriceResult(
        reference_price=Decimal(str(median(accepted))), accepted_values=accepted, outliers=outliers
    )


def decide_reference_price(
    values: list[Decimal],
    *,
    previous_reference: Decimal | None = None,
    minimum_samples: int = 2,
    maximum_jump_fraction: Decimal = Decimal("0.50"),
) -> ReferencePriceDecision:
    result = calculate_reference_price(values)
    reasons: list[PriceReviewReason] = []
    if len(result.accepted_values) < minimum_samples:
        reasons.append(PriceReviewReason.INSUFFICIENT_SAMPLES)
    if result.outliers:
        reasons.append(PriceReviewReason.OUTLIER)
    if previous_reference and abs(result.reference_price - previous_reference) / previous_reference > maximum_jump_fraction:
        reasons.append(PriceReviewReason.PRICE_JUMP)
    accepted = not reasons
    return ReferencePriceDecision(
        reference_price=result.reference_price if accepted or previous_reference is None else previous_reference,
        accepted=accepted,
        sample_count=len(result.accepted_values),
        review_reasons=tuple(reasons),
    )


async def retry_quotes[T](
    fetch: Callable[[], Awaitable[list[T]]], *, attempts: int, base_delay_seconds: float
) -> list[T]:
    for attempt in range(attempts):
        try:
            return await fetch()
        except ProviderRateLimitedError:
            if attempt + 1 == attempts:
                raise
            await asyncio.sleep(base_delay_seconds * (2**attempt))
    raise AssertionError("unreachable")
