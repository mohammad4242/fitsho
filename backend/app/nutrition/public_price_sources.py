"""Keyless public-page adapters for bounded canonical-food price discovery."""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from html.parser import HTMLParser
from typing import Any, Protocol, runtime_checkable
from urllib.parse import quote_plus, urljoin

import httpx

from app.nutrition.pricing import PriceObservation, ProviderRateLimitedError

_DIGIT_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_PACKAGE_PATTERN = re.compile(
    r"(?P<quantity>[0-9۰-۹٠-٩][0-9۰-۹٠-٩.,٬٫]*)\s*"
    r"(?P<unit>کیلوگرم|کیلو|گرم|میلی[‌\s-]*لیتر|لیتر|عدد|عددی|kg|g|ml|l)\b",
    re.IGNORECASE,
)
_UNIT_MAP = {
    "کیلوگرم": "kg",
    "کیلو": "kg",
    "گرم": "g",
    "میلیلیتر": "ml",
    "لیتر": "l",
    "عدد": "unit",
    "عددی": "unit",
    "kg": "kg",
    "g": "g",
    "ml": "ml",
    "l": "l",
}


@dataclass(frozen=True)
class PublicSourceDefinition:
    code: str
    name: str
    base_url: str
    search_url_template: str
    minimum_interval_seconds: float = 1.0
    parser_version: str = "public-page-v1"
    requires_api_key: bool = False

    def search_url(self, query: str) -> str:
        return urljoin(self.base_url, self.search_url_template.format(query=quote_plus(query)))


@dataclass(frozen=True)
class PublicProductCandidate:
    provider_code: str
    product_id: str
    title: str
    public_url: str
    currency: str
    normal_price: Decimal | None
    promotional_price: Decimal | None
    package_quantity: Decimal
    package_unit: str
    observed_at: datetime
    region: str | None = None
    parser_version: str = "public-page-v1"

    def to_observation(self) -> PriceObservation:
        return PriceObservation(
            provider_code=self.provider_code,
            provider_product_id=self.product_id,
            product_title=self.title,
            currency=self.currency,
            normal_price=self.normal_price,
            promotional_price=self.promotional_price,
            package_quantity=self.package_quantity,
            package_unit=self.package_unit,
            observed_at=self.observed_at,
            region=self.region,
        )


@runtime_checkable
class PublicDiscoveryProvider(Protocol):
    code: str
    uses_public_locators: bool

    async def discover(self, alias: str) -> list[PublicProductCandidate]: ...


PUBLIC_SOURCE_DEFINITIONS: tuple[PublicSourceDefinition, ...] = (
    PublicSourceDefinition(
        "digikala", "Digikala", "https://www.digikala.com/", "search/?q={query}"
    ),
    PublicSourceDefinition("torob", "Torob", "https://torob.com/", "search/?query={query}"),
    PublicSourceDefinition("basalam_public", "Basalam", "https://basalam.com/", "search?q={query}"),
    PublicSourceDefinition("okala", "Okala", "https://www.okala.com/", "search?q={query}"),
    PublicSourceDefinition(
        "snapp_market", "Snapp Market", "https://snapp.market/", "search?query={query}"
    ),
    PublicSourceDefinition(
        "hyperstar", "Hyperstar", "https://www.hyperstariran.com/", "search?q={query}"
    ),
    PublicSourceDefinition("shahrvand", "Shahrvand", "https://shahrvand.ir/", "search?q={query}"),
    PublicSourceDefinition("refah", "Refah", "https://refah.ir/", "search?q={query}"),
    PublicSourceDefinition("emalls", "Emalls", "https://emalls.ir/", "جستجو~SearchQuery~{query}"),
    PublicSourceDefinition(
        "tehran_market_official",
        "Tehran Market Official",
        "https://market.tehran.ir/",
        "search?q={query}",
    ),
)


class PublicProviderUnavailableError(RuntimeError):
    pass


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    normalized = str(value).translate(_DIGIT_TRANSLATION)
    normalized = normalized.replace("٬", "").replace(",", "").replace(" ", "")
    normalized = normalized.replace("٫", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def parse_package(title: str) -> tuple[Decimal, str] | None:
    normalized_title = title.replace("‌", "")
    normalized_title = re.sub(
        r"(?<!\S)یک\s*(?=کیلوگرم|کیلو|گرم|میلی\s*لیتر|لیتر|عدد)",
        "1 ",
        normalized_title,
    )
    match = _PACKAGE_PATTERN.search(normalized_title)
    if match is None:
        return None
    quantity = _decimal(match.group("quantity"))
    normalized_unit = match.group("unit").lower().replace("‌", "").replace(" ", "").replace("-", "")
    unit = _UNIT_MAP.get(normalized_unit)
    if quantity is None or quantity <= 0 or unit is None:
        return None
    return quantity, unit


def _walk_products(value: object) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            products.extend(_walk_products(item))
    elif isinstance(value, dict):
        item_type = value.get("@type")
        if item_type == "Product" or (isinstance(item_type, list) and "Product" in item_type):
            products.append(value)
        for key in ("itemListElement", "item", "mainEntity", "@graph"):
            if key in value:
                products.extend(_walk_products(value[key]))
    return products


class _StructuredProductParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.json_ld: list[str] = []
        self.table_rows: list[dict[str, str]] = []
        self._in_json_ld = False
        self._json_chunks: list[str] = []
        self._row: dict[str, str] | None = None
        self._title_chunks: list[str] = []
        self._in_title_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "script" and values.get("type", "").lower() == "application/ld+json":
            self._in_json_ld = True
            self._json_chunks = []
        if tag == "tr" and "data-product-id" in values:
            self._row = {
                "product_id": values["data-product-id"],
                "url": values.get("data-product-url", ""),
            }
            self._title_chunks = []
        if self._row is not None and tag == "td":
            if "data-title" in values:
                self._in_title_cell = True
            if "data-normal-price" in values:
                self._row["normal_price"] = values["data-normal-price"]
                self._row["currency"] = values.get("data-currency", "TOMAN")
            if "data-promotional-price" in values:
                self._row["promotional_price"] = values["data-promotional-price"]

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_json_ld:
            self.json_ld.append("".join(self._json_chunks))
            self._in_json_ld = False
        if tag == "td":
            self._in_title_cell = False
        if tag == "tr" and self._row is not None:
            self._row["title"] = "".join(self._title_chunks).strip()
            self.table_rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._in_json_ld:
            self._json_chunks.append(data)
        if self._in_title_cell:
            self._title_chunks.append(data)


def _candidate_from_product(
    *,
    provider_code: str,
    product: dict[str, Any],
    page_url: str,
    observed_at: datetime,
) -> PublicProductCandidate | None:
    title = str(product.get("name") or "").strip()
    package = parse_package(title)
    offers = product.get("offers")
    if not title or package is None or not isinstance(offers, dict):
        return None
    offer_price = _decimal(offers.get("price") or offers.get("lowPrice"))
    specification = offers.get("priceSpecification")
    normal_price = None
    if isinstance(specification, dict):
        normal_price = _decimal(specification.get("price"))
    promotional_price = (
        offer_price if normal_price is not None and offer_price != normal_price else None
    )
    if normal_price is None:
        normal_price = offer_price
    if normal_price is None:
        return None
    public_url = urljoin(page_url, str(product.get("url") or page_url))
    product_id = str(product.get("sku") or product.get("productID") or "").strip()
    if not product_id:
        product_id = sha256(public_url.encode()).hexdigest()[:32]
    quantity, unit = package
    return PublicProductCandidate(
        provider_code=provider_code,
        product_id=product_id,
        title=title,
        public_url=public_url,
        currency=str(offers.get("priceCurrency") or "TOMAN").upper(),
        normal_price=normal_price,
        promotional_price=promotional_price,
        package_quantity=quantity,
        package_unit=unit,
        observed_at=observed_at,
        region=str(offers.get("areaServed")) if offers.get("areaServed") else None,
    )


def parse_public_products(
    *, provider_code: str, html: str, page_url: str, observed_at: datetime
) -> list[PublicProductCandidate]:
    parser = _StructuredProductParser()
    parser.feed(html)
    candidates: list[PublicProductCandidate] = []
    for document in parser.json_ld:
        try:
            payload = json.loads(document)
        except json.JSONDecodeError:
            continue
        for product in _walk_products(payload):
            candidate = _candidate_from_product(
                provider_code=provider_code,
                product=product,
                page_url=page_url,
                observed_at=observed_at,
            )
            if candidate is not None:
                candidates.append(candidate)
    for row in parser.table_rows:
        package = parse_package(row.get("title", ""))
        normal_price = _decimal(row.get("normal_price"))
        if package is None or normal_price is None:
            continue
        quantity, unit = package
        candidates.append(
            PublicProductCandidate(
                provider_code=provider_code,
                product_id=row["product_id"],
                title=row["title"],
                public_url=urljoin(page_url, row.get("url") or page_url),
                currency=row.get("currency", "TOMAN").upper(),
                normal_price=normal_price,
                promotional_price=_decimal(row.get("promotional_price")),
                package_quantity=quantity,
                package_unit=unit,
                observed_at=observed_at,
            )
        )
    return list({(item.product_id, item.public_url): item for item in candidates}.values())


class PublicPageProvider:
    uses_public_locators = True

    def __init__(self, definition: PublicSourceDefinition, client: httpx.AsyncClient) -> None:
        self.definition = definition
        self.code = definition.code
        self._client = client
        self._last_request_at: float | None = None

    async def _request(self, url: str) -> httpx.Response:
        if self._last_request_at is not None:
            remaining = self.definition.minimum_interval_seconds - (
                time.monotonic() - self._last_request_at
            )
            if remaining > 0:
                await asyncio.sleep(remaining)
        response = await self._client.get(
            url,
            timeout=15,
            headers={"User-Agent": "FitshoPriceBot/1.0 (+public food price monitoring)"},
        )
        self._last_request_at = time.monotonic()
        if response.status_code == 429:
            raise ProviderRateLimitedError(f"{self.code} returned 429")
        if response.status_code in {401, 403}:
            raise PublicProviderUnavailableError(f"{self.code} denied public access")
        response.raise_for_status()
        return response

    async def discover(self, alias: str) -> list[PublicProductCandidate]:
        url = self.definition.search_url(alias)
        response = await self._request(url)
        return parse_public_products(
            provider_code=self.code,
            html=response.text,
            page_url=str(response.url),
            observed_at=datetime.now(UTC),
        )

    async def get_quotes(self, product_locators: list[str]) -> list[PriceObservation]:
        observations: list[PriceObservation] = []
        for locator in product_locators:
            response = await self._request(locator)
            candidates = parse_public_products(
                provider_code=self.code,
                html=response.text,
                page_url=str(response.url),
                observed_at=datetime.now(UTC),
            )
            observations.extend(candidate.to_observation() for candidate in candidates[:1])
        return observations
