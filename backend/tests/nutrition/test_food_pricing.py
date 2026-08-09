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
            package_quantity=Decimal("12"),
            package_unit="unit",
            normal_price=Decimal("180000"),
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


def test_reference_price_uses_mean_after_robust_outlier_rejection() -> None:
    from app.nutrition.pricing import calculate_reference_price

    result = calculate_reference_price(
        [Decimal("270000"), Decimal("285000"), Decimal("275000"), Decimal("920000")]
    )

    assert result.reference_price == Decimal("276666.6666666666666666666667")
    assert result.outliers == (Decimal("920000"),)


def test_reference_requires_three_distinct_sources() -> None:
    from app.nutrition.pricing import PriceReviewReason, decide_reference_price

    insufficient = decide_reference_price(
        [Decimal("270000"), Decimal("275000")], distinct_source_count=2
    )
    accepted = decide_reference_price(
        [Decimal("270000"), Decimal("275000"), Decimal("285000"), Decimal("920000")],
        distinct_source_count=4,
    )

    assert insufficient.accepted is False
    assert PriceReviewReason.INSUFFICIENT_SOURCES in insufficient.review_reasons
    assert accepted.accepted is True
    assert accepted.reference_price == Decimal("276666.6666666666666666666667")
    assert accepted.outliers == (Decimal("920000"),)


def test_large_change_requires_review_and_preserves_previous_price() -> None:
    from app.nutrition.pricing import PriceReviewReason, decide_reference_price

    decision = decide_reference_price(
        [Decimal("480000"), Decimal("500000")], previous_reference=Decimal("270000")
    )

    assert decision.accepted is False
    assert PriceReviewReason.PRICE_JUMP in decision.review_reasons
    assert decision.reference_price == Decimal("270000")


def test_extreme_source_disagreement_requires_review() -> None:
    from app.nutrition.pricing import PriceReviewReason, decide_reference_price

    decision = decide_reference_price(
        [Decimal("386000"), Decimal("733000"), Decimal("1660000")],
        distinct_source_count=3,
    )

    assert decision.accepted is False
    assert PriceReviewReason.SOURCE_DISAGREEMENT in decision.review_reasons


def test_insufficient_sources_requires_review() -> None:
    from app.nutrition.pricing import PriceReviewReason, decide_reference_price

    decision = decide_reference_price([Decimal("270000")])

    assert decision.accepted is False
    assert PriceReviewReason.INSUFFICIENT_SOURCES in decision.review_reasons


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
        NutritionOperationalEvent,
        NutritionPriceProvider,
    )
    from app.nutrition.price_update_service import run_price_update

    food = NutritionCatalogueFood(
        slug="price-test-chicken-breast",
        name_fa="سینه مرغ",
        name_en="Chicken breast",
        verification_status=FoodVerificationStatus.VERIFIED,
        source_name="test",
        source_reference="test",
    )
    providers = [
        NutritionPriceProvider(
            code=f"provider-{suffix}",
            kind=PriceProviderKind.PUBLIC_CATALOG,
            name=f"Provider {suffix.upper()}",
            enabled=True,
        )
        for suffix in ("a", "b", "c")
    ]
    db.add_all([food, *providers])
    db.flush()
    db.add_all(
        [
            NutritionFoodPriceMapping(
                food_id=food.id,
                provider_code=provider.code,
                provider_product_id=f"sku-{index}",
            )
            for index, provider in enumerate(providers, start=1)
        ]
    )
    db.commit()

    class Provider:
        def __init__(self, code: str, product_id: str, price: str) -> None:
            self.code = code
            self.product_id = product_id
            self.price = price

        async def get_quotes(self, _ids):
            return [
                observation(
                    provider_code=self.code,
                    provider_product_id=self.product_id,
                    normal_price=Decimal(self.price),
                ),
            ]

    provider_adapters = [
        Provider("provider-a", "sku-1", "243000"),
        Provider("provider-b", "sku-2", "250000"),
        Provider("provider-c", "sku-3", "247000"),
    ]
    first = run_price_update(
        db, providers=provider_adapters, scheduled_for=datetime(2026, 8, 8, 9, tzinfo=UTC)
    )
    same = run_price_update(
        db, providers=provider_adapters, scheduled_for=datetime(2026, 8, 8, 9, tzinfo=UTC)
    )

    assert same.id == first.id
    assert first.foods_updated == 1
    assert db.scalar(select(NutritionFoodPriceHistory)) is not None
    provider_event = db.scalar(
        select(NutritionOperationalEvent).where(
            NutritionOperationalEvent.category == "price_provider"
        )
    )
    assert provider_event is not None
    assert provider_event.provider == "provider-a"
    assert provider_event.status == "success"


def test_refresh_disables_mapping_when_product_no_longer_matches_canonical_food(db) -> None:
    from app.nutrition.enums import (
        EstimateConfidence,
        FoodVerificationStatus,
        PriceReferenceStatus,
    )
    from app.nutrition.models import (
        NutritionCatalogueFood,
        NutritionFoodPriceMapping,
        NutritionFoodPriceQuote,
        NutritionFoodPriceReference,
        NutritionFoodPriceReview,
    )
    from app.nutrition.price_update_service import run_price_update

    food = NutritionCatalogueFood(
        slug="mapping-drift-apple",
        name_fa="سیب",
        name_en="Apple",
        category="fruit",
        verification_status=FoodVerificationStatus.VERIFIED,
        source_name="test",
        source_reference="test",
    )
    db.add(food)
    db.flush()
    mapping = NutritionFoodPriceMapping(
        food_id=food.id,
        provider_code="digikala",
        provider_product_id="apple-vinegar",
        public_product_url="https://example.test/product/apple-vinegar",
        active=True,
    )
    db.add(mapping)
    reference = NutritionFoodPriceReference(
        food_id=food.id,
        canonical_unit="TOMAN_PER_KG",
        reference_price_toman=Decimal("120000"),
        sample_count=3,
        confidence=EstimateConfidence.HIGH,
        status=PriceReferenceStatus.ACCEPTED,
        calculated_at=datetime(2026, 8, 8, 8, tzinfo=UTC),
        accepted_at=datetime(2026, 8, 8, 8, tzinfo=UTC),
    )
    db.add(reference)
    db.commit()

    class DriftedProvider:
        code = "digikala"

        async def get_quotes(self, _ids):
            return [
                observation(
                    provider_code=self.code,
                    provider_product_id="apple-vinegar",
                    product_title="سرکه سیب طبیعی 1 لیتر",
                    package_quantity=Decimal("1"),
                    package_unit="l",
                    normal_price=Decimal("320000"),
                )
            ]

    run_price_update(
        db,
        providers=[DriftedProvider()],
        scheduled_for=datetime(2026, 8, 9, 12, tzinfo=UTC),
    )

    db.refresh(mapping)
    db.refresh(reference)
    review = db.scalar(
        select(NutritionFoodPriceReview).where(NutritionFoodPriceReview.food_id == food.id)
    )
    quote_count = len(
        db.scalars(
            select(NutritionFoodPriceQuote).where(NutritionFoodPriceQuote.food_id == food.id)
        ).all()
    )
    assert mapping.active is False
    assert mapping.broken_at is not None
    assert reference.status == PriceReferenceStatus.NEEDS_REVIEW
    assert reference.reference_price_toman == Decimal("120000")
    assert review is not None
    assert "ambiguous_match" in review.reason_codes
    assert quote_count == 0


def test_scheduler_uses_one_tehran_saturday_slot(test_settings) -> None:
    from app.nutrition.price_scheduler import is_due, most_recent_due_slot, weekly_slot

    saturday_after_noon = datetime(2026, 8, 8, 9, 30, tzinfo=UTC)  # 13:00 Tehran
    assert is_due(saturday_after_noon, test_settings) is True
    assert weekly_slot(saturday_after_noon, test_settings) == datetime(
        2026, 8, 8, 8, 30, tzinfo=UTC
    )
    assert most_recent_due_slot(datetime(2026, 8, 9, 8, tzinfo=UTC), test_settings) == datetime(
        2026, 8, 8, 8, 30, tzinfo=UTC
    )
    assert most_recent_due_slot(datetime(2026, 8, 8, 7, tzinfo=UTC), test_settings) == datetime(
        2026, 8, 1, 8, 30, tzinfo=UTC
    )
    assert most_recent_due_slot(datetime(2026, 8, 8, 8, 30, tzinfo=UTC), test_settings) == datetime(
        2026, 8, 8, 8, 30, tzinfo=UTC
    )


def test_empty_optional_api_key_keeps_only_keyless_public_providers(test_settings) -> None:
    import asyncio

    import httpx

    from app.nutrition.price_providers import configured_providers

    async def check() -> None:
        async with httpx.AsyncClient(trust_env=False) as client:
            providers = configured_providers(test_settings, client)
            assert [provider.code for provider in providers] == [
                "basalam_public",
                "digikala",
                "tapsi_shop",
            ]
            assert all(provider.code != "public_catalog" for provider in providers)

    asyncio.run(check())


def test_scheduler_commits_run_outside_advisory_lock_transaction(
    db, test_settings, monkeypatch
) -> None:
    import asyncio

    import httpx
    from sqlalchemy import delete

    from app.nutrition import price_scheduler
    from app.nutrition.models import NutritionFoodPriceUpdateRun

    engine = db.get_bind().engine
    monkeypatch.setattr(price_scheduler, "get_engine", lambda _url: engine)
    monkeypatch.setattr(price_scheduler, "configured_providers", lambda _settings, _client: [])
    due_now = datetime(2035, 8, 4, 8, 30, tzinfo=UTC)

    async def trigger() -> bool:
        async with httpx.AsyncClient(trust_env=False) as client:
            return await price_scheduler.trigger_scheduled_update(
                test_settings, client, now=due_now
            )

    assert asyncio.run(trigger()) is True
    with engine.begin() as connection:
        persisted = connection.scalar(
            select(NutritionFoodPriceUpdateRun.id).where(
                NutritionFoodPriceUpdateRun.scheduled_for == due_now
            )
        )
        assert persisted is not None
        connection.execute(
            delete(NutritionFoodPriceUpdateRun).where(
                NutritionFoodPriceUpdateRun.scheduled_for == due_now
            )
        )


def test_public_price_provider_registry_is_seeded_disabled_until_live_probe(db) -> None:
    from app.nutrition.models import NutritionPriceProvider

    providers = db.scalars(
        select(NutritionPriceProvider).order_by(NutritionPriceProvider.code)
    ).all()

    assert [provider.code for provider in providers] == [
        "basalam_public",
        "digikala",
        "emalls",
        "hyperstar",
        "okala",
        "refah",
        "shahrvand",
        "snapp_market",
        "tapsi_shop",
        "tehran_market_official",
        "torob",
    ]
    assert all(provider.enabled is False for provider in providers)
    assert all(provider.minimum_sources == 3 for provider in providers)
    assert next(provider for provider in providers if provider.code == "tapsi_shop").parser_version == (
        "tapsi-guest-v1"
    )


def test_first_public_run_discovers_mappings_and_accepts_three_source_mean(db) -> None:
    from app.auth.models import User
    from app.nutrition.enums import FoodVerificationStatus, PriceUpdateRunStatus
    from app.nutrition.models import (
        NutritionCatalogueFood,
        NutritionCatalogueFoodAlias,
        NutritionFoodPriceHistory,
        NutritionFoodPriceMapping,
        NutritionFoodPriceOverride,
        NutritionFoodPriceReference,
        NutritionPriceProvider,
    )
    from app.nutrition.price_update_service import run_price_update
    from app.nutrition.public_price_sources import PublicProductCandidate

    food = NutritionCatalogueFood(
        slug="discovery-test-grain",
        name_fa="دانه آزمایشی فیتشو",
        name_en="Fitsho test grain",
        verification_status=FoodVerificationStatus.VERIFIED,
        source_name="test",
        source_reference="test",
        category="grains",
    )
    admin = User(email="discovery-price-admin@example.com", password_hash="hash", is_admin=True)
    db.add_all([food, admin])
    db.flush()
    db.add(
        NutritionCatalogueFoodAlias(
            food_id=food.id,
            alias="دانه کشف قیمت",
            normalized_alias="دانه کشف قیمت",
            language="fa",
        )
    )
    override = NutritionFoodPriceOverride(
        food_id=food.id,
        reference_price_toman=Decimal("245000"),
        canonical_unit="TOMAN_PER_KG",
        reason="اصلاح موقت پیش از بروزرسانی بازار",
        created_by_user_id=admin.id,
        created_at=datetime(2026, 8, 8, 8, tzinfo=UTC),
        active=True,
    )
    db.add(override)
    db.commit()

    class DiscoveryProvider:
        uses_public_locators = True

        def __init__(self, code: str, price: str) -> None:
            self.code = code
            self.price = Decimal(price)

        async def discover(self, _alias: str):
            return [
                PublicProductCandidate(
                    provider_code=self.code,
                    product_id=f"{self.code}-rice",
                    title="دانه آزمایشی فیتشو ۱۰ کیلوگرم",
                    public_url=f"https://{self.code}.example/rice",
                    currency="TOMAN",
                    normal_price=self.price,
                    promotional_price=None,
                    package_quantity=Decimal("10"),
                    package_unit="kg",
                    observed_at=datetime(2026, 8, 9, 8, tzinfo=UTC),
                )
            ]

        async def get_quotes(self, _locators):
            raise AssertionError("newly discovered quotes must be reused")

    providers = [
        DiscoveryProvider("digikala", "2500000"),
        DiscoveryProvider("torob", "2600000"),
        DiscoveryProvider("basalam_public", "2550000"),
    ]
    run = run_price_update(
        db,
        providers=providers,
        scheduled_for=datetime(2026, 8, 9, 9, tzinfo=UTC),
    )

    reference = db.get(NutritionFoodPriceReference, food.id)
    history = db.scalar(
        select(NutritionFoodPriceHistory).where(NutritionFoodPriceHistory.food_id == food.id)
    )
    mappings = db.scalars(
        select(NutritionFoodPriceMapping).where(NutritionFoodPriceMapping.food_id == food.id)
    ).all()
    assert run.status == PriceUpdateRunStatus.COMPLETED_WITH_ERRORS
    assert run.foods_updated == 1
    assert reference is not None
    assert reference.reference_price_toman == Decimal("255000")
    assert len(mappings) == 3
    assert all(mapping.public_product_url for mapping in mappings)
    assert history is not None
    assert len(history.accepted_quote_ids) == 3
    assert history.rejected_quote_ids == []
    assert override.active is False
    assert override.expired_by_run_id == run.id
    assert all(db.get(NutritionPriceProvider, provider.code).enabled for provider in providers)


def test_public_refresh_reuses_existing_sku_from_bounded_search_without_detail_batch(db) -> None:
    from app.nutrition.enums import FoodVerificationStatus
    from app.nutrition.models import (
        NutritionCatalogueFood,
        NutritionFoodPriceMapping,
        NutritionFoodPriceQuote,
    )
    from app.nutrition.price_update_service import run_price_update
    from app.nutrition.public_price_sources import PublicProductCandidate

    food = NutritionCatalogueFood(
        slug="search-refresh-lentil",
        name_fa="عدس تست قیمت",
        name_en="Price test lentil",
        category="legumes",
        verification_status=FoodVerificationStatus.VERIFIED,
        source_name="test",
        source_reference="test",
    )
    db.add(food)
    db.flush()
    mapping = NutritionFoodPriceMapping(
        food_id=food.id,
        provider_code="digikala",
        provider_product_id="same-sku",
        public_product_url="https://example.test/product/same-sku",
        active=True,
    )
    db.add(mapping)
    db.commit()

    class SearchProvider:
        code = "digikala"
        uses_public_locators = True

        async def discover(self, _alias: str):
            return [
                PublicProductCandidate(
                    provider_code=self.code,
                    product_id="same-sku",
                    title="عدس تست قیمت 900 گرم",
                    public_url="https://example.test/product/same-sku",
                    currency="TOMAN",
                    normal_price=Decimal("300000"),
                    promotional_price=None,
                    package_quantity=Decimal("900"),
                    package_unit="g",
                    observed_at=datetime(2026, 8, 9, 8, tzinfo=UTC),
                )
            ]

        async def get_quotes(self, _locators):
            raise AssertionError("bounded search observation must avoid detail refresh")

    run_price_update(
        db,
        providers=[SearchProvider()],
        scheduled_for=datetime(2026, 8, 9, 13, tzinfo=UTC),
    )

    quotes = db.scalars(
        select(NutritionFoodPriceQuote).where(NutritionFoodPriceQuote.food_id == food.id)
    ).all()
    assert len(quotes) == 1
    assert quotes[0].provider_product_id == "same-sku"


def test_zero_provider_run_is_observable_error_not_success(db) -> None:
    from app.nutrition.enums import PriceUpdateRunStatus
    from app.nutrition.price_update_service import run_price_update

    run = run_price_update(
        db,
        providers=[],
        scheduled_for=datetime(2026, 8, 9, 10, tzinfo=UTC),
    )

    assert run.status == PriceUpdateRunStatus.COMPLETED_WITH_ERRORS
    assert "NO_PROVIDERS" in run.failure_codes
    assert "NO_USABLE_OBSERVATIONS" in run.failure_codes


def test_discovery_failure_is_visible_in_provider_health(db) -> None:
    from app.nutrition.models import NutritionPriceProvider
    from app.nutrition.price_update_service import run_price_update

    class FailingDiscoveryProvider:
        code = "digikala"
        uses_public_locators = True

        async def discover(self, _alias: str):
            raise RuntimeError("temporary public source failure")

        async def get_quotes(self, _locators):
            return []

    run = run_price_update(
        db,
        providers=[FailingDiscoveryProvider()],
        scheduled_for=datetime(2026, 8, 9, 11, tzinfo=UTC),
    )

    provider = db.get(NutritionPriceProvider, "digikala")
    assert run.provider_failures == 1
    assert provider is not None
    assert provider.last_error == "provider discovery failed"
