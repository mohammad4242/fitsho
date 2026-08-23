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
    INSUFFICIENT_SOURCES = "insufficient_sources"


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
    outliers: tuple[Decimal, ...] = ()


@dataclass(frozen=True)
class PublicPricePolicy:
    version: str = "public-price-v3"
    minimum_distinct_sources: int = 3
    mad_multiplier: Decimal = Decimal("3.5")
    maximum_jump_fraction: Decimal = Decimal("0.50")
    maximum_source_spread_fraction: Decimal = Decimal("0.75")


DEFAULT_PUBLIC_PRICE_POLICY = PublicPricePolicy()


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


def calculate_reference_price(
    values: list[Decimal],
    policy: PublicPricePolicy = DEFAULT_PUBLIC_PRICE_POLICY,
) -> ReferencePriceResult:
    if not values:
        raise PriceValidationError("No price quotes")
    ordered = sorted(values)
    centre = Decimal(str(median(ordered)))
    deviations = [abs(value - centre) for value in ordered]
    mad = Decimal(str(median(deviations)))
    if mad > 0:
        accepted = tuple(
            value for value in ordered if abs(value - centre) <= mad * policy.mad_multiplier
        )
    else:
        lower_half = ordered[: len(ordered) // 2]
        upper_half = ordered[(len(ordered) + 1) // 2 :]
        lower_quartile = Decimal(str(median(lower_half))) if lower_half else centre
        upper_quartile = Decimal(str(median(upper_half))) if upper_half else centre
        iqr = upper_quartile - lower_quartile
        accepted = tuple(
            value
            for value in ordered
            if lower_quartile - Decimal("1.5") * iqr
            <= value
            <= upper_quartile + Decimal("1.5") * iqr
        )
    outliers = tuple(value for value in ordered if value not in accepted)
    if not accepted:
        accepted = tuple(ordered)
    return ReferencePriceResult(
        reference_price=sum(accepted, Decimal()) / Decimal(len(accepted)),
        accepted_values=accepted,
        outliers=outliers,
    )


def decide_reference_price(
    values: list[Decimal],
    *,
    previous_reference: Decimal | None = None,
    distinct_source_count: int | None = None,
    policy: PublicPricePolicy = DEFAULT_PUBLIC_PRICE_POLICY,
) -> ReferencePriceDecision:
    result = calculate_reference_price(values, policy)
    reasons: list[PriceReviewReason] = []
    source_count = distinct_source_count if distinct_source_count is not None else len(values)
    if source_count < policy.minimum_distinct_sources:
        reasons.append(PriceReviewReason.INSUFFICIENT_SOURCES)
    if len(result.accepted_values) >= 2:
        accepted_median = Decimal(str(median(result.accepted_values)))
        source_spread = (
            max(result.accepted_values) - min(result.accepted_values)
        ) / accepted_median
        if source_spread > policy.maximum_source_spread_fraction:
            reasons.append(PriceReviewReason.SOURCE_DISAGREEMENT)
    if previous_reference and abs(result.reference_price - previous_reference) / previous_reference > policy.maximum_jump_fraction:
        reasons.append(PriceReviewReason.PRICE_JUMP)
    accepted = not reasons
    return ReferencePriceDecision(
        reference_price=result.reference_price if accepted or previous_reference is None else previous_reference,
        accepted=accepted,
        sample_count=len(result.accepted_values),
        review_reasons=tuple(reasons),
        outliers=result.outliers,
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
