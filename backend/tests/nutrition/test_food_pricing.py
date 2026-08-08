# ruff: noqa: E501
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select


def observation(**changes: object):
    from app.nutrition.pricing import PriceObservation

    values: dict[str, object] = {
        "provider_code": "public_catalog",
        "provider_product_id": "sku-1",
        "product_title": "سینه مرغ تازه 900 گرم",
        "currency": "TOMAN",
        "normal_price": Decimal("243000"),
        "promotional_price": None,
        "package_quantity": Decimal("900"),
        "package_unit": "g",
        "observed_at": datetime.now(UTC),
        "region": "tehran",
    }
    values.update(changes)
    return PriceObservation(**values)  # type: ignore[arg-type]


def test_normalizes_grams_to_toman_per_kg() -> None:
    from app.nutrition.pricing import normalize_observation

    quote = normalize_observation(observation())

    assert quote.normalized_normal_price == Decimal("270000")
    assert quote.canonical_unit == "TOMAN_PER_KG"


def test_normalizes_liters_and_units_and_keeps_promotion_separate() -> None:
    from app.nutrition.pricing import normalize_observation

    milk = normalize_observation(
        observation(package_quantity=Decimal("1"), package_unit="l", normal_price=Decimal("80000"))
    )
    eggs = normalize_observation(
        observation(
            package_quantity=Decimal("12"), package_unit="unit", normal_price=Decimal("180000"),
            promotional_price=Decimal("150000"),
        )
    )

    assert milk.normalized_normal_price == Decimal("80000")
    assert milk.canonical_unit == "TOMAN_PER_LITER"
    assert eggs.normalized_normal_price == Decimal("15000")
    assert eggs.normalized_promotional_price == Decimal("12500")
    assert eggs.is_promotional is True


def test_rejects_invalid_package_size() -> None:
    from app.nutrition.pricing import PriceValidationError, normalize_observation

    with pytest.raises(PriceValidationError, match="package"):
        normalize_observation(observation(package_quantity=Decimal("0")))


def test_classifies_fresh_stale_estimated_and_unavailable() -> None:
    from app.nutrition.pricing import PriceFreshness, classify_freshness

    now = datetime.now(UTC)
    assert classify_freshness(now - timedelta(hours=2), now, 24, 168) is PriceFreshness.FRESH
    assert classify_freshness(now - timedelta(hours=48), now, 24, 168) is PriceFreshness.STALE
    assert classify_freshness(now - timedelta(hours=200), now, 24, 168) is PriceFreshness.ESTIMATED
    assert classify_freshness(None, now, 24, 168) is PriceFreshness.UNAVAILABLE


def test_reference_price_uses_median_after_outlier_rejection() -> None:
    from app.nutrition.pricing import calculate_reference_price

    result = calculate_reference_price(
        [Decimal("270000"), Decimal("285000"), Decimal("275000"), Decimal("920000")]
    )

    assert result.reference_price == Decimal("275000")
    assert result.outliers == (Decimal("920000"),)


def test_large_change_requires_review_and_preserves_previous_price() -> None:
    from app.nutrition.pricing import PriceReviewReason, decide_reference_price

    decision = decide_reference_price(
        [Decimal("480000"), Decimal("500000")], previous_reference=Decimal("270000")
    )

    assert decision.accepted is False
    assert PriceReviewReason.PRICE_JUMP in decision.review_reasons
    assert decision.reference_price == Decimal("270000")


def test_insufficient_samples_requires_review() -> None:
    from app.nutrition.pricing import PriceReviewReason, decide_reference_price

    decision = decide_reference_price([Decimal("270000")])

    assert decision.accepted is False
    assert PriceReviewReason.INSUFFICIENT_SAMPLES in decision.review_reasons


def test_retries_rate_limited_provider_without_fabricating_quote() -> None:
    from app.nutrition.pricing import ProviderRateLimitedError, retry_quotes

    attempts = 0

    async def fetch() -> list[object]:
        nonlocal attempts
        attempts += 1
        raise ProviderRateLimitedError("429")

    with pytest.raises(ProviderRateLimitedError):
        import asyncio

        asyncio.run(retry_quotes(fetch, attempts=2, base_delay_seconds=0))
    assert attempts == 2


def test_update_run_is_idempotent_and_preserves_previous_price_on_review(db) -> None:
    from app.nutrition.enums import FoodVerificationStatus, PriceProviderKind
    from app.nutrition.models import (
        NutritionCatalogueFood,
        NutritionFoodPriceHistory,
        NutritionFoodPriceMapping,
        NutritionPriceProvider,
    )
    from app.nutrition.price_update_service import run_price_update

    food = NutritionCatalogueFood(
        slug="chicken-breast", name_fa="سینه مرغ", name_en="Chicken breast",
        verification_status=FoodVerificationStatus.VERIFIED, source_name="test", source_reference="test",
    )
    provider = NutritionPriceProvider(code="provider-a", kind=PriceProviderKind.PUBLIC_CATALOG, name="Provider A", enabled=True)
    db.add_all([food, provider])
    db.flush()
    db.add_all([
        NutritionFoodPriceMapping(food_id=food.id, provider_code=provider.code, provider_product_id="sku-1"),
        NutritionFoodPriceMapping(food_id=food.id, provider_code=provider.code, provider_product_id="sku-2"),
    ])
    db.commit()

    class Provider:
        code = "provider-a"

        async def get_quotes(self, _ids):
            return [
                observation(provider_code=self.code),
                observation(provider_code=self.code, provider_product_id="sku-2", normal_price=Decimal("250000")),
            ]

    first = run_price_update(db, providers=[Provider()], scheduled_for=datetime(2026, 8, 8, 9, tzinfo=UTC))
    same = run_price_update(db, providers=[Provider()], scheduled_for=datetime(2026, 8, 8, 9, tzinfo=UTC))

    assert same.id == first.id
    assert first.foods_updated == 1
    assert db.scalar(select(NutritionFoodPriceHistory)) is not None


def test_scheduler_uses_one_tehran_saturday_slot(test_settings) -> None:
    from app.nutrition.price_scheduler import is_due, weekly_slot

    saturday_after_noon = datetime(2026, 8, 8, 9, 30, tzinfo=UTC)  # 13:00 Tehran
    assert is_due(saturday_after_noon, test_settings) is True
    assert weekly_slot(saturday_after_noon, test_settings) == datetime(2026, 8, 8, 8, 30, tzinfo=UTC)


def test_empty_optional_api_key_does_not_enable_a_provider(test_settings) -> None:
    import asyncio

    import httpx

    from app.nutrition.price_providers import configured_providers

    async def check() -> None:
        async with httpx.AsyncClient(trust_env=False) as client:
            assert configured_providers(test_settings, client) == []

    asyncio.run(check())
