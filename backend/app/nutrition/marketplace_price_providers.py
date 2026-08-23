"""Concrete keyless adapters for the approved Iranian food-price sources."""

from __future__ import annotations

import asyncio
import re
import time
from datetime import UTC, datetime
from decimal import Decimal
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse

import httpx

from app.nutrition.pricing import PriceObservation, ProviderRateLimitedError
from app.nutrition.public_price_sources import (
    PublicProductCandidate,
    PublicProviderUnavailableError,
    _decimal,
    parse_package,
)

_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36"
)
_PRODUCT_ID_PATTERN = re.compile(r"/product/(?:dkp-)?(?P<id>[0-9]+)")


class _RateLimitedProvider:
    minimum_interval_seconds = 1.0

    def __init__(self) -> None:
        self._last_request_at: float | None = None

    async def _wait(self) -> None:
        if self._last_request_at is not None:
            remaining = self.minimum_interval_seconds - (time.monotonic() - self._last_request_at)
            if remaining > 0:
                await asyncio.sleep(remaining)
        self._last_request_at = time.monotonic()


def _package_from_marketplace_product(
    payload: dict[str, object], title: str
) -> tuple[Decimal, str] | None:
    main_attribute = str(payload.get("mainAttribute") or "").strip()
    package = parse_package(main_attribute) or parse_package(title)
    if package is not None:
        return package
    weight = _decimal(payload.get("weight"))
    if weight is not None and weight > 0:
        return weight, "g"
    quantity = _decimal(payload.get("unit_quantity"))
    unit_type = payload.get("unit_type")
    if quantity is not None and isinstance(unit_type, dict):
        unit_name = str(unit_type.get("name") or "").replace("‌", "")
        parsed = parse_package(f"{quantity} {unit_name}")
        if parsed is not None:
            return parsed
    return None


class BasalamPublicProvider(_RateLimitedProvider):
    code = "basalam_public"
    uses_public_locators = True

    def __init__(self, client: httpx.AsyncClient) -> None:
        super().__init__()
        self._client = client

    async def _request(
        self, method: str, url: str, *, json_data: dict[str, object] | None = None
    ) -> httpx.Response:
        await self._wait()
        response = await self._client.request(method, url, timeout=20, json=json_data)
        if response.status_code == 429:
            raise ProviderRateLimitedError("basalam_public returned 429")
        response.raise_for_status()
        return response

    @staticmethod
    def _candidate(
        payload: dict[str, object], observed_at: datetime
    ) -> PublicProductCandidate | None:
        title = str(payload.get("name") or payload.get("title") or "").strip()
        package = _package_from_marketplace_product(payload, title)
        selling_price = _decimal(payload.get("price"))
        normal_price = _decimal(payload.get("primaryPrice") or payload.get("primary_price"))
        if not title or package is None or selling_price is None:
            return None
        normal_price = normal_price or selling_price
        promotional_price = selling_price if selling_price != normal_price else None
        owner = payload.get("vendor")
        region: str | None = None
        if isinstance(owner, dict):
            owner_value = owner.get("owner")
            if isinstance(owner_value, dict) and owner_value.get("city"):
                region = str(owner_value["city"])
            city = owner.get("city")
            if region is None and isinstance(city, dict) and city.get("name"):
                region = str(city["name"])
        product_id = str(payload.get("id") or "").strip()
        if not product_id:
            return None
        quantity, unit = package
        return PublicProductCandidate(
            provider_code=BasalamPublicProvider.code,
            product_id=product_id,
            title=title,
            public_url=f"https://basalam.com/p/{product_id}",
            currency="IRR",
            normal_price=normal_price,
            promotional_price=promotional_price,
            package_quantity=quantity,
            package_unit=unit,
            observed_at=observed_at,
            region=region,
            parser_version="basalam-public-v1",
        )

    async def discover(self, alias: str) -> list[PublicProductCandidate]:
        response = await self._request(
            "POST",
            "https://openapi.basalam.com/v1/products/search",
            json_data={"q": alias, "rows": 24, "start": 0},
        )
        payload = response.json()
        rows = payload.get("products", []) if isinstance(payload, dict) else []
        observed_at = datetime.now(UTC)
        return [
            candidate
            for row in rows
            if isinstance(row, dict)
            and bool(row.get("IsAvailable", True))
            and bool(row.get("IsSaleable", True))
            and (candidate := self._candidate(row, observed_at)) is not None
        ]

    async def get_quotes(self, product_locators: list[str]) -> list[PriceObservation]:
        quotes: list[PriceObservation] = []
        for locator in product_locators:
            match = _PRODUCT_ID_PATTERN.search(locator)
            product_id = match.group("id") if match else locator
            try:
                response = await self._request(
                    "GET", f"https://openapi.basalam.com/v1/products/{product_id}"
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in {404, 410}:
                    continue
                raise
            payload = response.json()
            if isinstance(payload, dict):
                candidate = self._candidate(payload, datetime.now(UTC))
                if candidate is not None:
                    quotes.append(candidate.to_observation())
        return quotes


class DigikalaPublicProvider(_RateLimitedProvider):
    code = "digikala"
    uses_public_locators = True

    def __init__(self, client: httpx.AsyncClient) -> None:
        super().__init__()
        self._client = client

    async def _get(self, url: str) -> httpx.Response:
        await self._wait()
        response = await self._client.get(
            url,
            timeout=20,
            headers={"User-Agent": _BROWSER_USER_AGENT, "Accept": "application/json"},
            follow_redirects=False,
        )
        if response.status_code == 307 and response.headers.get("location") == str(response.url):
            response = await self._client.get(
                url,
                timeout=20,
                headers={"User-Agent": _BROWSER_USER_AGENT, "Accept": "application/json"},
                follow_redirects=False,
            )
        if response.status_code == 429:
            raise ProviderRateLimitedError("digikala returned 429")
        if response.status_code in {401, 403}:
            raise PublicProviderUnavailableError("digikala denied public access")
        response.raise_for_status()
        return response

    @staticmethod
    def _candidate(
        payload: dict[str, object], observed_at: datetime
    ) -> PublicProductCandidate | None:
        title = str(payload.get("title_fa") or "").strip()
        package = parse_package(title)
        variant = payload.get("default_variant")
        if not title or package is None or not isinstance(variant, dict):
            return None
        price = variant.get("price")
        if not isinstance(price, dict):
            return None
        selling_price = _decimal(price.get("selling_price"))
        normal_price = _decimal(price.get("rrp_price")) or selling_price
        if selling_price is None or normal_price is None:
            return None
        promotional_price = selling_price if selling_price != normal_price else None
        product_id = str(payload.get("id") or "").strip()
        if not product_id:
            return None
        product_url = payload.get("url")
        if isinstance(product_url, dict):
            product_url = product_url.get("uri")
        quantity, unit = package
        return PublicProductCandidate(
            provider_code=DigikalaPublicProvider.code,
            product_id=product_id,
            title=title,
            public_url=urljoin(
                "https://www.digikala.com/", str(product_url or f"product/dkp-{product_id}/")
            ),
            currency="IRR",
            normal_price=normal_price,
            promotional_price=promotional_price,
            package_quantity=quantity,
            package_unit=unit,
            observed_at=observed_at,
            parser_version="digikala-public-v1",
        )

    async def discover(self, alias: str) -> list[PublicProductCandidate]:
        response = await self._get(
            f"https://api.digikala.com/v1/search/?q={quote(alias, safe='')}&page=1"
        )
        payload = response.json()
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        rows = data.get("products", []) if isinstance(data, dict) else []
        observed_at = datetime.now(UTC)
        return [
            candidate
            for row in rows
            if isinstance(row, dict)
            and (candidate := self._candidate(row, observed_at)) is not None
        ]

    async def get_quotes(self, product_locators: list[str]) -> list[PriceObservation]:
        quotes: list[PriceObservation] = []
        for locator in product_locators:
            match = _PRODUCT_ID_PATTERN.search(locator)
            product_id = match.group("id") if match else locator
            try:
                response = await self._get(
                    f"https://api.digikala.com/v2/product/{product_id}/"
                )
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in {404, 410}:
                    continue
                raise
            payload = response.json()
            data = payload.get("data", {}) if isinstance(payload, dict) else {}
            product = data.get("product") if isinstance(data, dict) else None
            if isinstance(product, dict):
                candidate = self._candidate(product, datetime.now(UTC))
                if candidate is not None:
                    quotes.append(candidate.to_observation())
        return quotes


class _TapsiSearchParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict[str, object]] = []
        self._row: dict[str, object] | None = None
        self._price_kind: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if (
            self._row is None
            and tag == "a"
            and values.get("data-test-name") == "product-card-redirect-to-product-action"
        ):
            self._row = {"href": values.get("href", ""), "texts": [], "prices": {}}
            return
        if self._row is not None:
            test_name = values.get("data-test-name")
            if test_name in {"product-card-original-price", "product-card-final-price"}:
                self._price_kind = test_name

    def handle_endtag(self, tag: str) -> None:
        if self._row is None:
            return
        if tag == "span":
            self._price_kind = None
        if tag == "a":
            self.rows.append(self._row)
            self._row = None
            self._price_kind = None

    def handle_data(self, data: str) -> None:
        if self._row is None:
            return
        value = data.strip()
        if not value:
            return
        texts = self._row["texts"]
        prices = self._row["prices"]
        assert isinstance(texts, list)
        assert isinstance(prices, dict)
        texts.append(value)
        if self._price_kind:
            prices[self._price_kind] = f"{prices.get(self._price_kind, '')}{value}"


def parse_tapsi_rendered_products(
    *, html: str, page_url: str, observed_at: datetime
) -> list[PublicProductCandidate]:
    parser = _TapsiSearchParser()
    parser.feed(html)
    products: list[PublicProductCandidate] = []
    for row in parser.rows:
        href = str(row["href"])
        match = _PRODUCT_ID_PATTERN.search(href)
        texts = row["texts"]
        prices = row["prices"]
        assert isinstance(texts, list)
        assert isinstance(prices, dict)
        title = next((text for text in texts if parse_package(str(text)) is not None), "")
        package = parse_package(str(title))
        final_price = _decimal(prices.get("product-card-final-price"))
        original_price = _decimal(prices.get("product-card-original-price")) or final_price
        if match is None or package is None or final_price is None or original_price is None:
            continue
        quantity, unit = package
        query = parse_qs(urlparse(href).query)
        store_id = query.get("store_id", [None])[0]
        products.append(
            PublicProductCandidate(
                provider_code="tapsi_shop",
                product_id=match.group("id"),
                title=str(title),
                public_url=urljoin(page_url, href),
                currency="TOMAN",
                normal_price=original_price,
                promotional_price=final_price if final_price != original_price else None,
                package_quantity=quantity,
                package_unit=unit,
                observed_at=observed_at,
                region=f"store:{store_id}" if store_id else None,
                parser_version="tapsi-rendered-v1",
            )
        )
    return products


class _TapsiDetailParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: str | None = None
        self.prices: dict[str, str] = {}
        self._price_kind: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "meta" and values.get("property") == "og:title":
            self.title = values.get("content")
        test_name = values.get("data-test-name")
        if test_name in {"productDetail-original-price", "productDetail-final-price"}:
            self._price_kind = test_name

    def handle_endtag(self, tag: str) -> None:
        self._price_kind = None

    def handle_data(self, data: str) -> None:
        if self._price_kind:
            self.prices[self._price_kind] = f"{self.prices.get(self._price_kind, '')}{data.strip()}"


def parse_tapsi_rendered_detail(
    *, html: str, page_url: str, observed_at: datetime
) -> PublicProductCandidate | None:
    parser = _TapsiDetailParser()
    parser.feed(html)
    match = _PRODUCT_ID_PATTERN.search(page_url)
    title = (parser.title or "").removeprefix("قیمت و خرید ").split(" | ", maxsplit=1)[0]
    if not title:
        path_parts = [
            unquote(part).replace("-", " ") for part in urlparse(page_url).path.split("/")
        ]
        title = next((part for part in reversed(path_parts) if part and not part.isdigit()), "")
    package = parse_package(title)
    final_price = _decimal(parser.prices.get("productDetail-final-price"))
    original_price = _decimal(parser.prices.get("productDetail-original-price")) or final_price
    if match is None or package is None or final_price is None or original_price is None:
        return None
    quantity, unit = package
    store_id = parse_qs(urlparse(page_url).query).get("store_id", [None])[0]
    return PublicProductCandidate(
        provider_code="tapsi_shop",
        product_id=match.group("id"),
        title=title,
        public_url=page_url,
        currency="TOMAN",
        normal_price=original_price,
        promotional_price=final_price if final_price != original_price else None,
        package_quantity=quantity,
        package_unit=unit,
        observed_at=observed_at,
        region=f"store:{store_id}" if store_id else None,
        parser_version="tapsi-rendered-v1",
    )


class TapsiShopProvider(_RateLimitedProvider):
    code = "tapsi_shop"
    uses_public_locators = True

    def __init__(self, client: httpx.AsyncClient) -> None:
        super().__init__()
        self._client = client
        self._access_token: str | None = None
        self._session_id: str | None = None

    async def _ensure_guest_session(self) -> None:
        if self._access_token and self._session_id:
            return
        csrf_response = await self._client.get(
            "https://tapsi.shop/api/auth/v4/csrf", timeout=20
        )
        csrf_response.raise_for_status()
        csrf_token = csrf_response.json().get("csrfToken")
        if not isinstance(csrf_token, str) or not csrf_token:
            raise PublicProviderUnavailableError("tapsi_shop guest CSRF token is unavailable")
        callback_response = await self._client.post(
            "https://tapsi.shop/api/auth/v4/callback/GUEST",
            data={
                "csrfToken": csrf_token,
                "callbackUrl": "https://tapsi.shop",
                "json": "true",
            },
            headers={"Origin": "https://tapsi.shop", "Referer": "https://tapsi.shop/"},
            timeout=20,
        )
        callback_response.raise_for_status()
        session_response = await self._client.get(
            "https://tapsi.shop/api/auth/v4/session", timeout=20
        )
        session_response.raise_for_status()
        session = session_response.json()
        access_token = session.get("accessToken") if isinstance(session, dict) else None
        session_id = session.get("sessionId") if isinstance(session, dict) else None
        if not isinstance(access_token, str) or not isinstance(session_id, str):
            raise PublicProviderUnavailableError("tapsi_shop guest session is unavailable")
        self._access_token = access_token
        self._session_id = session_id

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_data: dict[str, object] | None = None,
        retry_session: bool = True,
    ) -> httpx.Response:
        await self._wait()
        await self._ensure_guest_session()
        response = await self._client.request(
            method,
            f"https://qcommercegw.tapsi.shop{path}",
            json=json_data,
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "clientSessionId": self._session_id or "",
                "client-version": "0.1.43",
                "client-name": "qcommerce.tapsi.shop",
                "Content-Type": "application/json-patch+json",
                "Referer": "https://tapsi.shop/",
            },
            timeout=20,
        )
        if response.status_code == 429:
            raise ProviderRateLimitedError("tapsi_shop returned 429")
        if response.status_code in {401, 403} and retry_session:
            self._access_token = None
            self._session_id = None
            return await self._request(
                method, path, json_data=json_data, retry_session=False
            )
        response.raise_for_status()
        return response

    @staticmethod
    def _candidate(
        product: dict[str, object],
        *,
        observed_at: datetime,
        store_id: str | None,
    ) -> PublicProductCandidate | None:
        if not bool(product.get("availability", True)):
            return None
        title = str(product.get("name") or "").strip()
        package = parse_package(title)
        final_price = _decimal(product.get("finalPrice"))
        normal_price = _decimal(product.get("originalPrice")) or final_price
        product_id = str(product.get("hsin") or product.get("id") or "").strip()
        if (
            not title
            or package is None
            or final_price is None
            or normal_price is None
            or not product_id
        ):
            return None
        quantity, unit = package
        query = f"?store_id={quote(store_id, safe='')}" if store_id else ""
        region = f"store:{store_id}" if store_id else None
        return PublicProductCandidate(
            provider_code=TapsiShopProvider.code,
            product_id=product_id,
            title=title,
            public_url=f"https://tapsi.shop/product/{product_id}{query}",
            currency="TOMAN",
            normal_price=normal_price,
            promotional_price=final_price if final_price != normal_price else None,
            package_quantity=quantity,
            package_unit=unit,
            observed_at=observed_at,
            region=region,
            parser_version="tapsi-guest-v1",
        )

    async def discover(self, alias: str) -> list[PublicProductCandidate]:
        response = await self._request(
            "POST",
            "/View/v3/SearchView",
            json_data={
                "term": alias,
                "finalExpressDeterminations": [],
                "collectionId": None,
                "storeId": None,
                "attributeFilters": [],
                "canDeliverInPerson": False,
                "isPurchaseCouponOnly": False,
                "pageSize": 24,
                "pageNumber": 1,
                "searchOption": 3,
            },
        )
        payload = response.json()
        data = payload.get("data", {}) if isinstance(payload, dict) else {}
        result = data.get("searchResult", {}) if isinstance(data, dict) else {}
        rows = result.get("items", []) if isinstance(result, dict) else []
        observed_at = datetime.now(UTC)
        candidates: list[PublicProductCandidate] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            product = row.get("product")
            store = row.get("store")
            if not isinstance(product, dict):
                continue
            store_id = str(store.get("id")) if isinstance(store, dict) and store.get("id") else None
            candidate = self._candidate(
                product,
                observed_at=observed_at,
                store_id=store_id,
            )
            if candidate is not None:
                candidates.append(candidate)
        return candidates

    async def get_quotes(self, product_locators: list[str]) -> list[PriceObservation]:
        quotes: list[PriceObservation] = []
        for locator in product_locators:
            match = _PRODUCT_ID_PATTERN.search(locator)
            product_id = match.group("id") if match else locator
            try:
                response = await self._request("GET", f"/Product/Detail/{product_id}")
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in {404, 410}:
                    continue
                raise
            payload = response.json()
            data = payload.get("data", {}) if isinstance(payload, dict) else {}
            products = data.get("uniqueProducts", []) if isinstance(data, dict) else []
            product = next(
                (
                    item
                    for item in products
                    if isinstance(item, dict)
                    and str(item.get("hsin") or item.get("id")) == product_id
                ),
                None,
            )
            candidate = (
                self._candidate(
                    product,
                    observed_at=datetime.now(UTC),
                    store_id=str(data.get("storeId")) if data.get("storeId") else None,
                )
                if isinstance(product, dict) and isinstance(data, dict)
                else None
            )
            if candidate is not None:
                quotes.append(candidate.to_observation())
        return quotes
