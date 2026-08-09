from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx

from app.nutrition.pricing import ProviderRateLimitedError
from app.nutrition.public_price_matching import CanonicalFoodIdentity, match_candidate
from app.nutrition.public_price_sources import (
    PUBLIC_SOURCE_DEFINITIONS,
    PublicPageProvider,
    parse_public_products,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "nutrition" / "prices"


def test_json_ld_parser_handles_persian_digits_packages_and_promotion() -> None:
    products = parse_public_products(
        provider_code="digikala",
        html=FIXTURES.joinpath("public_search.html").read_text(),
        page_url="https://market.example/search?q=rice",
        observed_at=datetime(2026, 8, 9, 8, tzinfo=UTC),
    )

    rice = products[0]
    assert rice.product_id == "rice-10kg-1"
    assert rice.package_quantity == Decimal("10")
    assert rice.package_unit == "kg"
    assert rice.normal_price == Decimal("28000000")
    assert rice.promotional_price == Decimal("25000000")
    assert rice.currency == "IRR"


def test_official_table_parser_handles_toman_and_gram_package() -> None:
    products = parse_public_products(
        provider_code="tehran_market_official",
        html=FIXTURES.joinpath("official_table.html").read_text(),
        page_url="https://prices.example/",
        observed_at=datetime(2026, 8, 9, 8, tzinfo=UTC),
    )

    assert products[0].package_quantity == Decimal("900")
    assert products[0].package_unit == "g"
    assert products[0].normal_price == Decimal("243000")
    assert products[0].currency == "TOMAN"


def test_matching_accepts_alias_and_rejects_supplements_bundles_and_ambiguity() -> None:
    candidates = parse_public_products(
        provider_code="basalam_public",
        html=FIXTURES.joinpath("public_search.html").read_text(),
        page_url="https://market.example/search?q=rice",
        observed_at=datetime(2026, 8, 9, 8, tzinfo=UTC),
    )
    food = CanonicalFoodIdentity(
        slug="iranian-rice",
        name_fa="برنج ایرانی",
        category="grains",
        aliases=("برنج ایرانی", "برنج هاشمی"),
    )

    assert match_candidate(food, candidates[0]).accepted is True
    assert match_candidate(food, candidates[1]).accepted is False


def test_all_ten_public_sources_are_independent_and_keyless() -> None:
    assert {source.code for source in PUBLIC_SOURCE_DEFINITIONS} == {
        "digikala",
        "torob",
        "basalam_public",
        "okala",
        "snapp_market",
        "hyperstar",
        "shahrvand",
        "refah",
        "emalls",
        "tehran_market_official",
    }
    assert all(source.requires_api_key is False for source in PUBLIC_SOURCE_DEFINITIONS)
    assert all(source.minimum_interval_seconds >= 1 for source in PUBLIC_SOURCE_DEFINITIONS)


def test_public_provider_treats_429_as_rate_limit_without_retrying_privately() -> None:
    import asyncio

    async def check() -> None:
        async def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(429)

        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        provider = PublicPageProvider(PUBLIC_SOURCE_DEFINITIONS[0], client)
        try:
            await provider.discover("برنج ایرانی")
        except ProviderRateLimitedError:
            pass
        else:
            raise AssertionError("429 must be surfaced as a provider rate limit")
        finally:
            await client.aclose()

    asyncio.run(check())
