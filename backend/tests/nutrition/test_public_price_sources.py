from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx

from app.config import Settings
from app.nutrition.marketplace_price_providers import (
    BasalamPublicProvider,
    DigikalaPublicProvider,
    TapsiShopProvider,
    parse_tapsi_rendered_products,
)
from app.nutrition.pricing import ProviderRateLimitedError
from app.nutrition.public_price_matching import CanonicalFoodIdentity, match_candidate
from app.nutrition.public_price_sources import (
    PUBLIC_SOURCE_DEFINITIONS,
    PublicPageProvider,
    PublicProductCandidate,
    parse_package,
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


def test_package_parser_prefers_written_one_kilogram_before_tolerance() -> None:
    assert parse_package("سینه مرغ یک کیلوگرم ±50 گرم") == (Decimal("1"), "kg")


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


def test_matching_rejects_seed_snacks_and_pet_food_false_positives() -> None:
    observed_at = datetime(2026, 8, 9, 8, tzinfo=UTC)

    def candidate(title: str) -> PublicProductCandidate:
        return PublicProductCandidate(
            provider_code="tapsi_shop",
            product_id=title,
            title=title,
            public_url="https://example.test/product/1",
            currency="TOMAN",
            normal_price=Decimal("100000"),
            promotional_price=None,
            package_quantity=Decimal("500"),
            package_unit="g",
            observed_at=observed_at,
        )

    watermelon = CanonicalFoodIdentity("watermelon", "هندوانه", "fruit", ("هندوانه",))
    white_fish = CanonicalFoodIdentity("white-fish", "ماهی سفید", "protein", ("ماهی سفید",))

    assert match_candidate(watermelon, candidate("تخمه هندوانه 500 گرم")).accepted is False
    assert (
        match_candidate(white_fish, candidate("غذای گربه پوچ ماهی سفید 85 گرم")).accepted is False
    )
    false_matches = (
        ("سیب", "fruit", "سرکه سیب طبیعی 1 لیتر"),
        ("موز", "fruit", "موز خشک 250 گرم"),
        ("بروکلی", "vegetable", "تابلو پل بروکلین 3 عددی"),
        ("کره", "fat", "کره بادام زمینی 300 گرم"),
        ("هویج", "vegetable", "اسپری برنزه هویج 250 میلی لیتر"),
        ("کرفس", "vegetable", "تخم کرفس 75 گرم"),
        ("خیار", "vegetable", "خیار شور 250 گرم"),
        ("خرما", "fruit", "چیپس خرما 500 گرم"),
        ("بادمجان", "vegetable", "قیمه بادمجان 285 گرم"),
        ("انگور", "fruit", "شیره انگور 500 گرم"),
        ("پیاز", "vegetable", "اسنک پیاز و جعفری 250 گرم"),
        ("ماکارونی", "grain", "ادویه ماکارونی 100 گرم"),
        ("ماست ساده", "dairy", "ماست چکیده موسیر 700 گرم"),
        ("گوجه فرنگی", "vegetable", "سس گوجه فرنگی 660 گرم"),
        ("هندوانه", "fruit", "پاستیل هندوانه 500 گرم"),
    )
    for name, category, title in false_matches:
        identity = CanonicalFoodIdentity(name, name, category, (name,))
        assert match_candidate(identity, candidate(title)).accepted is False, title


def test_matching_rejects_real_marketplace_non_raw_food_false_positives() -> None:
    observed_at = datetime(2026, 8, 9, 8, tzinfo=UTC)

    def candidate(title: str) -> PublicProductCandidate:
        return PublicProductCandidate(
            provider_code="public_test",
            product_id=title,
            title=title,
            public_url="https://example.test/product/1",
            currency="TOMAN",
            normal_price=Decimal("100000"),
            promotional_price=None,
            package_quantity=Decimal("500"),
            package_unit="g",
            observed_at=observed_at,
        )

    false_matches = (
        ("بادمجان", "بادمجان سرخ شده منجمد 500 گرم"),
        ("بادمجان", "خوراک بادمجان کبابی 400 گرم"),
        ("سیب زمینی", "پوره کن سیب زمینی استیل"),
        ("سیب زمینی", "کوکو سیب زمینی آماده 500 گرم"),
        ("سینه مرغ", "شینسل سینه مرغ 900 گرم"),
        ("نارنگی", "کره بدن نارنگی 200 میلی لیتر"),
        ("نارنگی", "بالم لب نارنگی 10 گرم"),
        ("پیاز", "پیاز گل اگزالیس 5 عدد"),
        ("پیاز", "پیاز داغ آماده 250 گرم"),
        ("بادام زمینی", "بادام زمینی با طعم کچاپ 250 گرم"),
        ("ذرت", "ذرت پاپ کرن 500 گرم"),
        ("قارچ", "قارچ کفیر 50 گرم"),
        ("نخود", "میکروب یا گرده شبتاب نخود 100 گرم"),
        ("خیار", "خیار بوته ای ارکا بذر ایرانیان"),
        ("خیار", "چاشنی ماست و خیار سحرخیز 55 گرم"),
        ("ذرت", "ذرت مخصوص پاپ کردن 200 گرم"),
        ("ذرت", "ذرت پفیلای درجه یک 500 گرم"),
        ("بادام زمینی", "بادام زمینی بوداده کم نمک 500 گرم"),
        ("ماست ساده", "ماست ساز خانگی"),
        ("ماست ساده", "ماست سبزیجات 750 گرم"),
        ("توت فرنگی", "توت فرنگی گیفت"),
    )
    for name, title in false_matches:
        identity = CanonicalFoodIdentity(name, name, "test", (name,))
        assert match_candidate(identity, candidate(title)).accepted is False, title


def test_matching_requires_skinless_label_for_skinless_chicken_thigh() -> None:
    observed_at = datetime(2026, 8, 9, 8, tzinfo=UTC)

    def candidate(title: str) -> PublicProductCandidate:
        return PublicProductCandidate(
            provider_code="public_test",
            product_id=title,
            title=title,
            public_url="https://example.test/product/1",
            currency="TOMAN",
            normal_price=Decimal("500000"),
            promotional_price=None,
            package_quantity=Decimal("1"),
            package_unit="kg",
            observed_at=observed_at,
        )

    food = CanonicalFoodIdentity(
        "chicken-thigh-skinless",
        "ران مرغ بدون پوست",
        "poultry",
        ("ران مرغ", "ران مرغ بدون پوست"),
    )
    assert match_candidate(food, candidate("ران مرغ 1 کیلوگرم")).accepted is False
    assert match_candidate(food, candidate("ران مرغ بدون پوست 1 کیلوگرم")).accepted is True


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


def test_configured_live_providers_are_only_the_three_approved_free_sources() -> None:
    from app.nutrition.price_providers import configured_providers

    async def check() -> None:
        transport = httpx.MockTransport(lambda _: httpx.Response(200))
        async with httpx.AsyncClient(transport=transport) as client:
            providers = configured_providers(Settings(), client)
        assert [provider.code for provider in providers] == [
            "basalam_public",
            "digikala",
            "tapsi_shop",
        ]

    import asyncio

    asyncio.run(check())


def test_basalam_public_search_returns_traceable_package_prices() -> None:
    import asyncio

    async def check() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            assert request.url.path == "/v1/products/search"
            return httpx.Response(
                200,
                json={
                    "products": [
                        {
                            "id": 101,
                            "name": "برنج هاشمی 10 کیلوگرم",
                            "price": 36000000,
                            "primaryPrice": 40000000,
                            "mainAttribute": "10000 گرم",
                            "weight": 10000,
                            "vendor": {"owner": {"city": "رشت"}},
                            "IsAvailable": True,
                            "IsSaleable": True,
                        }
                    ]
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            products = await BasalamPublicProvider(client).discover("برنج هاشمی")

        assert len(products) == 1
        assert products[0].product_id == "101"
        assert products[0].normal_price == Decimal("40000000")
        assert products[0].promotional_price == Decimal("36000000")
        assert products[0].package_quantity == Decimal("10000")
        assert products[0].package_unit == "g"
        assert products[0].currency == "IRR"
        assert products[0].region == "رشت"

    asyncio.run(check())


def test_basalam_refresh_skips_removed_product_without_losing_other_quotes() -> None:
    import asyncio

    async def check() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            product_id = request.url.path.rsplit("/", maxsplit=1)[-1]
            if product_id == "missing":
                return httpx.Response(404)
            return httpx.Response(
                200,
                json={
                    "id": product_id,
                    "name": f"عدس {product_id} وزن 900 گرم",
                    "price": 2_200_000,
                    "primaryPrice": 2_500_000,
                    "mainAttribute": "900 گرم",
                    "weight": 900,
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            quotes = await BasalamPublicProvider(client).get_quotes(["101", "missing", "102"])

        assert [quote.provider_product_id for quote in quotes] == ["101", "102"]

    asyncio.run(check())


def test_digikala_public_search_retries_cdn_cookie_challenge_once() -> None:
    import asyncio

    async def check() -> None:
        attempts = 0

        async def handler(request: httpx.Request) -> httpx.Response:
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return httpx.Response(
                    307,
                    headers={
                        "location": str(request.url),
                        "set-cookie": "digicdn_cookie=test; Domain=.digikala.com; Path=/",
                    },
                )
            return httpx.Response(
                200,
                json={
                    "status": 200,
                    "data": {
                        "products": [
                            {
                                "id": 202,
                                "title_fa": "عدس درشت 900 گرم",
                                "url": {"uri": "/product/dkp-202/"},
                                "default_variant": {
                                    "price": {
                                        "selling_price": 2200000,
                                        "rrp_price": 2500000,
                                        "discount_percent": 12,
                                    }
                                },
                            }
                        ]
                    },
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            products = await DigikalaPublicProvider(client).discover("عدس")

        assert attempts == 2
        assert products[0].normal_price == Decimal("2500000")
        assert products[0].promotional_price == Decimal("2200000")
        assert products[0].currency == "IRR"
        assert products[0].package_quantity == Decimal("900")
        assert products[0].package_unit == "g"

    asyncio.run(check())


def test_tapsi_rendered_search_extracts_title_package_and_both_prices() -> None:
    html = """
    <a data-test-name="product-card-redirect-to-product-action"
       href="/product/303/rice?store_id=44">
      <span>3 ساعت</span>
      <span>برنج شیرودی درجه یک 10 کیلوگرم</span>
      <span>فروشگاه نمونه</span>
      <span data-test-name="product-card-original-price">4,390,000</span>
      <span data-test-name="product-card-final-price">3,951,000</span>
    </a>
    """

    products = parse_tapsi_rendered_products(
        html=html,
        page_url="https://tapsi.shop/search?term=برنج",
        observed_at=datetime(2026, 8, 9, 8, tzinfo=UTC),
    )

    assert len(products) == 1
    assert products[0].product_id == "303"
    assert products[0].normal_price == Decimal("4390000")
    assert products[0].promotional_price == Decimal("3951000")
    assert products[0].currency == "TOMAN"
    assert products[0].package_quantity == Decimal("10")
    assert products[0].package_unit == "kg"
    assert products[0].region == "store:44"


def test_tapsi_rendered_search_keeps_cards_separate_when_images_are_void_tags() -> None:
    html = """
    <a data-test-name="product-card-redirect-to-product-action" href="/product/501/rice-a">
      <img src="a.jpg">
      <span>برنج ایرانی 10 کیلوگرم</span>
      <span data-test-name="product-card-original-price">4,000,000</span>
      <span data-test-name="product-card-final-price">3,800,000</span>
    </a>
    <a data-test-name="product-card-redirect-to-product-action" href="/product/502/rice-b">
      <img src="b.jpg">
      <span>برنج خارجی 5 کیلوگرم</span>
      <span data-test-name="product-card-final-price">1,500,000</span>
    </a>
    """

    products = parse_tapsi_rendered_products(
        html=html,
        page_url="https://tapsi.shop/search?term=برنج",
        observed_at=datetime(2026, 8, 9, 8, tzinfo=UTC),
    )

    assert [(item.product_id, item.normal_price) for item in products] == [
        ("501", Decimal("4000000")),
        ("502", Decimal("1500000")),
    ]


def test_tapsi_provider_uses_keyless_guest_catalogue_for_search_and_refresh() -> None:
    import asyncio

    async def check() -> None:
        requests: list[tuple[str, str]] = []

        async def handler(request: httpx.Request) -> httpx.Response:
            requests.append((request.method, request.url.path))
            if request.url.path == "/api/auth/v4/csrf":
                return httpx.Response(200, json={"csrfToken": "csrf-test"})
            if request.url.path == "/api/auth/v4/callback/GUEST":
                return httpx.Response(200, json={"url": "https://tapsi.shop"})
            if request.url.path == "/api/auth/v4/session":
                return httpx.Response(
                    200,
                    json={"accessToken": "guest-token", "sessionId": "guest-session"},
                )
            assert request.headers["authorization"] == "Bearer guest-token"
            assert request.headers["clientSessionId"] == "guest-session"
            if request.url.path == "/View/v3/SearchView":
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "searchResult": {
                                "items": [
                                    {
                                        "store": {"id": "44", "name": "فروشگاه نمونه"},
                                        "product": {
                                            "hsin": "303",
                                            "slug": "غذای-ایرانی" * 100,
                                            "name": "برنج ایرانی 10 کیلوگرم",
                                            "originalPrice": 4_390_000,
                                            "finalPrice": 3_951_000,
                                            "currency": "تومان",
                                            "availability": True,
                                        },
                                    }
                                ]
                            }
                        }
                    },
                )
            if request.url.path == "/Product/Detail/303":
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "storeId": "44",
                            "storeName": "فروشگاه نمونه",
                            "uniqueProducts": [
                                {
                                    "hsin": "303",
                                    "slug": "rice",
                                    "name": "برنج ایرانی 10 کیلوگرم",
                                    "originalPrice": 4_500_000,
                                    "finalPrice": 4_050_000,
                                    "currency": "تومان",
                                    "availability": True,
                                }
                            ],
                        }
                    },
                )
            raise AssertionError(f"Unexpected request: {request.method} {request.url}")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            provider = TapsiShopProvider(client)
            products = await provider.discover("برنج")
            quotes = await provider.get_quotes([products[0].public_url])

        assert products[0].normal_price == Decimal("4390000")
        assert products[0].promotional_price == Decimal("3951000")
        assert products[0].region == "store:44"
        assert len(products[0].public_url) < 500
        assert quotes[0].normal_price == Decimal("4500000")
        assert quotes[0].promotional_price == Decimal("4050000")
        assert requests.count(("GET", "/api/auth/v4/session")) == 1

    asyncio.run(check())
