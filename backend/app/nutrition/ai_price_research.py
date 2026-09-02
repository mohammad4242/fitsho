"""Backend-owned Agent Service research for current Iranian food prices."""

from __future__ import annotations

import ipaddress
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from hashlib import sha256
from typing import Literal
from urllib.parse import SplitResult, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.body_analysis.providers.models import (
    ModelRoute,
    ProviderRoutingPreferences,
    StructuredGenerationRequest,
    StructuredGenerationResponse,
)
from app.body_analysis.providers.protocol import AIProvider
from app.nutrition.pricing import (
    PriceObservation,
    PriceReviewReason,
    PriceValidationError,
    normalize_observation,
)
from app.nutrition.public_price_matching import CanonicalFoodIdentity, match_candidate
from app.nutrition.public_price_sources import PublicProductCandidate

FOOD_PRICE_RESEARCH_SCHEMA_NAME = "fitsho_food_price_research_v1"
MEDIAN_BAND_FRACTION = Decimal("0.20")
MAX_RESEARCH_SOURCES = 5
INITIAL_RESEARCH_SOURCES = 3

FOOD_PRICE_RESEARCH_SYSTEM_PROMPT = """You are Fitsho's public Iranian food-price research agent.

This is a bounded evidence task and requires live web research. Use the live web/search/fetch tool exposed by your runner for this request. Do not
answer from model memory. Return only one JSON object matching the supplied
response schema and only evidence actually observed during this request. Do not answer from model memory.

The input contains `task`, `as_of_date`, `market`, `food`,
`requested_source_count`, and `excluded_domains`. Research the exact food in
the stated public Iranian retail market. In the first pass, return no more than
the requested source count (normally three). If the first pass does not form a
coherent independent-source cluster, the Backend may make one bounded
expansion request for the remaining sources, up to five total.

For every quote, preserve the exact observed product or listing title, package
quantity and unit, normal non-promotional price, any separate promotional
price, explicit currency (`TOMAN` or `IRR`), source name, and a real public
public HTTPS URL observed during this request. Use at most one quote from each
canonical domain, with at most one quote from each independent domain. Never use
a domain listed in `excluded_domains`.
Prefer public, current retail evidence. Reject unrelated, prepared, bulk,
bundled, ambiguous, or stale results. Do not turn a search result into a
product URL, and do not invent, estimate, copy from memory, or fabricate a
price, product, source, or URL.

The Backend owns food matching, normalization, unit comparability, validation,
median calculation, reference-price promotion, and review decisions. Do not calculate the Fitsho reference price or return it. Return only observed evidence;
do not provide medical advice or personal data.
"""

_IRANIAN_MULTI_LABEL_SUFFIXES = {
    "ac.ir",
    "co.ir",
    "gov.ir",
    "net.ir",
    "org.ir",
}
_COMMON_MULTI_LABEL_SUFFIXES = {
    "co.uk",
    "com.au",
    "com.br",
    "com.cn",
    "com.tr",
    "co.nz",
    "co.za",
    "org.uk",
}


def _hostname_from_url(source_url: str) -> tuple[SplitResult, str]:
    if not source_url or len(source_url) > 500:
        raise ValueError("Source URL is empty or too long")
    try:
        parsed = urlsplit(source_url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as error:
        raise ValueError("Malformed source URL") from error
    if parsed.scheme.lower() != "https":
        raise ValueError("Source URL must use HTTPS")
    if not hostname:
        raise ValueError("Source URL must have a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Source URL cannot contain credentials")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Source URL has an invalid port")

    normalized_hostname = hostname.rstrip(".").lower()
    try:
        normalized_hostname = normalized_hostname.encode("idna").decode("ascii")
    except UnicodeError as error:
        raise ValueError("Source URL has an invalid hostname") from error
    if not normalized_hostname:
        raise ValueError("Source URL must have a hostname")
    if (
        normalized_hostname == "localhost"
        or normalized_hostname.endswith(".localhost")
        or normalized_hostname.endswith(".local")
    ):
        raise ValueError("Local source hosts are not allowed")
    try:
        ip_address = ipaddress.ip_address(normalized_hostname)
    except ValueError:
        ip_address = None
    if ip_address is not None and not ip_address.is_global:
        raise ValueError("Private or local source IPs are not allowed")
    if any(ord(character) < 32 for character in normalized_hostname):
        raise ValueError("Source URL has an invalid hostname")
    return parsed, normalized_hostname


def canonical_source_url(source_url: str) -> str:
    """Return a stable public URL identity for a researched page."""

    parsed, hostname = _hostname_from_url(source_url)
    if hostname.startswith("www."):
        hostname = hostname[4:]
    host = hostname
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        pass
    else:
        if ":" in hostname:
            host = f"[{hostname}]"
    if parsed.port is not None and parsed.port != 443:
        host = f"{host}:{parsed.port}"
    return urlunsplit(("https", host, parsed.path, parsed.query, ""))


def canonical_source_domain(source_url: str) -> str:
    """Derive a conservative independent retail domain from a public URL."""

    _, hostname = _hostname_from_url(source_url)
    if hostname.startswith("www."):
        hostname = hostname[4:]
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        labels = [label for label in hostname.split(".") if label]
        if len(labels) <= 2:
            return ".".join(labels)
        suffix = ".".join(labels[-2:])
        if suffix in _IRANIAN_MULTI_LABEL_SUFFIXES | _COMMON_MULTI_LABEL_SUFFIXES:
            return ".".join(labels[-3:])
        return ".".join(labels[-2:])
    else:
        return hostname


def _canonical_excluded_domain(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise ValueError("Excluded source domain cannot be empty")
    if "://" not in candidate:
        candidate = f"https://{candidate}/"
    return canonical_source_domain(candidate)


@dataclass(frozen=True)
class FoodPriceResearchFood:
    slug: str
    name_fa: str
    name_en: str
    category: str
    aliases: tuple[str, ...] = ()

    def to_matching_identity(self) -> CanonicalFoodIdentity:
        return CanonicalFoodIdentity(
            slug=self.slug,
            name_fa=self.name_fa,
            category=self.category,
            aliases=self.aliases,
        )


def _non_blank(value: str, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} cannot be blank")
    return value


class FoodPriceResearchQuote(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_name: str = Field(min_length=1, max_length=160)
    source_url: str = Field(min_length=1, max_length=500)
    product_title: str = Field(min_length=1, max_length=500)
    normal_price: Decimal = Field(gt=0)
    promotional_price: Decimal | None = Field(default=None, gt=0)
    currency: Literal["TOMAN", "IRR"]
    package_quantity: Decimal = Field(gt=0)
    package_unit: Literal["g", "kg", "ml", "l", "unit", "item"]
    region: str | None = Field(default=None, max_length=120)

    @field_validator("source_name")
    @classmethod
    def validate_source_name(cls, value: str) -> str:
        return _non_blank(value, "source_name")

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        canonical_source_url(value)
        return value

    @field_validator("product_title")
    @classmethod
    def validate_product_title(cls, value: str) -> str:
        return _non_blank(value, "product_title")

    @field_validator("region")
    @classmethod
    def validate_region(cls, value: str | None) -> str | None:
        return None if value is None or value.strip() else value


class FoodPriceResearchOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    food_slug: str = Field(min_length=1, max_length=120)
    quotes: tuple[FoodPriceResearchQuote, ...] = Field(default=(), max_length=5)

    @field_validator("food_slug")
    @classmethod
    def validate_food_slug(cls, value: str) -> str:
        return _non_blank(value, "food_slug")


def build_food_price_research_request(
    food: FoodPriceResearchFood,
    *,
    route: ModelRoute,
    requested_source_count: int,
    excluded_domains: Iterable[str] = (),
    as_of_date: date | None = None,
    provider_preferences: ProviderRoutingPreferences | None = None,
    temperature: float = 0.0,
    max_output_tokens: int = 4096,
) -> StructuredGenerationRequest:
    if not 1 <= requested_source_count <= MAX_RESEARCH_SOURCES:
        raise ValueError("Requested source count must be between one and five")
    normalized_excluded_domains = sorted(
        {_canonical_excluded_domain(value) for value in excluded_domains}
    )
    input_payload = {
        "task": "research_current_iran_food_retail_prices",
        "as_of_date": (as_of_date or datetime.now(UTC).date()).isoformat(),
        "market": "Iran",
        "food": {
            "slug": food.slug,
            "name_fa": food.name_fa,
            "name_en": food.name_en,
            "category": food.category,
            "aliases": list(food.aliases),
        },
        "requested_source_count": requested_source_count,
        "excluded_domains": normalized_excluded_domains,
    }
    return StructuredGenerationRequest(
        system_prompt=FOOD_PRICE_RESEARCH_SYSTEM_PROMPT,
        input_payload=input_payload,
        response_schema=FoodPriceResearchOutput.model_json_schema(),
        schema_name=FOOD_PRICE_RESEARCH_SCHEMA_NAME,
        route=route,
        provider_preferences=provider_preferences or ProviderRoutingPreferences(),
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        web_access="live",
    )


def _median(values: Sequence[Decimal]) -> Decimal:
    if not values:
        raise ValueError("Cannot calculate a median for no values")
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / Decimal("2")


def median_band_indices(
    values: Sequence[Decimal],
    *,
    fraction: Decimal = MEDIAN_BAND_FRACTION,
) -> tuple[int, ...]:
    """Return input indexes whose values fall inside the inclusive median band."""

    if not values:
        return ()
    if fraction < 0:
        raise ValueError("Median band fraction cannot be negative")
    centre = _median(values)
    if centre <= 0:
        raise ValueError("Median must be positive")
    return tuple(
        index for index, value in enumerate(values) if abs(value - centre) / centre <= fraction
    )


@dataclass(frozen=True)
class FoodPriceResearchEvidence:
    observation: PriceObservation
    source_name: str
    source_url: str
    source_domain: str
    product_title: str
    provider_code: str
    provider_product_id: str
    normalized_normal_price_toman: Decimal
    canonical_unit: str
    match_accepted: bool
    match_reason_code: str | None
    agent_request_id: str | None


@dataclass(frozen=True)
class AgentFoodPriceResearchResult:
    evidence: tuple[FoodPriceResearchEvidence, ...]
    request_ids: tuple[str, ...]
    expanded: bool


class FoodPriceResearchError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        reason: PriceReviewReason = PriceReviewReason.INSUFFICIENT_SOURCES,
        evidence: tuple[FoodPriceResearchEvidence, ...] = (),
        request_ids: tuple[str, ...] = (),
        expanded: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.reason = reason
        self.evidence = evidence
        self.request_ids = request_ids
        self.expanded = expanded


def _provider_code(source_domain: str) -> str:
    return f"agent_web_{sha256(source_domain.encode('utf-8')).hexdigest()[:16]}"


def _provider_product_id(source_url: str) -> str:
    return sha256(source_url.encode("utf-8")).hexdigest()[:32]


def _request_id(response: StructuredGenerationResponse) -> str | None:
    if response.provider_request_id is None:
        return None
    return response.provider_request_id[:160]


class AgentFoodPriceResearcher:
    def __init__(
        self,
        provider: AIProvider,
        *,
        route: ModelRoute,
        preferences: ProviderRoutingPreferences | None = None,
        temperature: float = 0.0,
        max_output_tokens: int = 4096,
        initial_source_count: int = INITIAL_RESEARCH_SOURCES,
        max_sources: int = MAX_RESEARCH_SOURCES,
    ) -> None:
        if initial_source_count != INITIAL_RESEARCH_SOURCES:
            raise ValueError("Food price research must start with three sources")
        if max_sources != MAX_RESEARCH_SOURCES:
            raise ValueError("Food price research maximum is five sources")
        self.provider = provider
        self.route = route
        self.preferences = preferences or ProviderRoutingPreferences()
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    async def research(
        self,
        food: FoodPriceResearchFood,
        *,
        expand_sources: bool = True,
    ) -> AgentFoodPriceResearchResult:
        evidence: list[FoodPriceResearchEvidence] = []
        domains: set[str] = set()
        request_ids: list[str] = []

        first_response = await self._request(
            food,
            requested_source_count=INITIAL_RESEARCH_SOURCES,
            excluded_domains=(),
            request_ids=request_ids,
            evidence=tuple(evidence),
            expanded=False,
        )
        self._append_response_evidence(
            first_response,
            food,
            evidence=evidence,
            domains=domains,
            requested_source_count=INITIAL_RESEARCH_SOURCES,
            request_id=request_ids[-1] if request_ids else None,
            request_ids=tuple(request_ids),
            expanded=False,
        )

        if not evidence or self._has_trusted_initial_cluster(evidence) or not expand_sources:
            return AgentFoodPriceResearchResult(tuple(evidence), tuple(request_ids), False)

        additional_count = min(MAX_RESEARCH_SOURCES - len(domains), MAX_RESEARCH_SOURCES)
        if additional_count > 0:
            second_response = await self._request(
                food,
                requested_source_count=additional_count,
                excluded_domains=domains,
                request_ids=request_ids,
                evidence=tuple(evidence),
                expanded=True,
            )
            self._append_response_evidence(
                second_response,
                food,
                evidence=evidence,
                domains=domains,
                requested_source_count=additional_count,
                request_id=request_ids[-1] if request_ids else None,
                request_ids=tuple(request_ids),
                expanded=True,
            )
        return AgentFoodPriceResearchResult(tuple(evidence), tuple(request_ids), True)

    async def _request(
        self,
        food: FoodPriceResearchFood,
        *,
        requested_source_count: int,
        excluded_domains: Iterable[str],
        request_ids: list[str],
        evidence: tuple[FoodPriceResearchEvidence, ...],
        expanded: bool,
    ) -> StructuredGenerationResponse:
        request = build_food_price_research_request(
            food,
            route=self.route,
            requested_source_count=requested_source_count,
            excluded_domains=excluded_domains,
            provider_preferences=self.preferences,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )
        try:
            response = await self.provider.generate_structured_text(request)
        except Exception as error:
            raise FoodPriceResearchError(
                "Agent price research request failed",
                code="request_failed",
                evidence=evidence,
                request_ids=tuple(request_ids),
                expanded=expanded,
            ) from error
        request_id = _request_id(response)
        if request_id is not None:
            request_ids.append(request_id)
        return response

    def _parse_response(
        self,
        response: StructuredGenerationResponse,
        *,
        food: FoodPriceResearchFood,
        evidence: tuple[FoodPriceResearchEvidence, ...],
        request_ids: tuple[str, ...],
        expanded: bool,
    ) -> FoodPriceResearchOutput:
        try:
            parsed = FoodPriceResearchOutput.model_validate(response.payload)
        except ValidationError as error:
            raise FoodPriceResearchError(
                "Agent returned invalid price research output",
                code="malformed_response",
                evidence=evidence,
                request_ids=request_ids,
                expanded=expanded,
            ) from error
        if parsed.food_slug != food.slug:
            raise FoodPriceResearchError(
                "Agent returned evidence for a different food",
                code="food_mismatch",
                reason=PriceReviewReason.AMBIGUOUS_MATCH,
                evidence=evidence,
                request_ids=request_ids,
                expanded=expanded,
            )
        return parsed

    def _append_response_evidence(
        self,
        response: StructuredGenerationResponse,
        food: FoodPriceResearchFood,
        *,
        evidence: list[FoodPriceResearchEvidence],
        domains: set[str],
        requested_source_count: int,
        request_id: str | None,
        request_ids: tuple[str, ...],
        expanded: bool,
    ) -> None:
        parsed = self._parse_response(
            response,
            food=food,
            evidence=tuple(evidence),
            request_ids=request_ids,
            expanded=expanded,
        )
        for quote in parsed.quotes[:requested_source_count]:
            try:
                source_url = canonical_source_url(quote.source_url)
                source_domain = canonical_source_domain(source_url)
            except ValueError:
                continue
            if source_domain in domains or len(domains) >= MAX_RESEARCH_SOURCES:
                continue
            observation = PriceObservation(
                provider_code=_provider_code(source_domain),
                provider_product_id=_provider_product_id(source_url),
                product_title=quote.product_title,
                currency=quote.currency,
                normal_price=quote.normal_price,
                promotional_price=quote.promotional_price,
                package_quantity=quote.package_quantity,
                package_unit=quote.package_unit,
                observed_at=datetime.now(UTC),
                region=quote.region,
            )
            try:
                normalized = normalize_observation(observation)
            except PriceValidationError:
                continue
            if normalized.normalized_normal_price is None:
                continue
            candidate = PublicProductCandidate(
                provider_code=observation.provider_code,
                product_id=observation.provider_product_id,
                title=observation.product_title,
                public_url=source_url,
                currency=observation.currency,
                normal_price=observation.normal_price,
                promotional_price=observation.promotional_price,
                package_quantity=observation.package_quantity,
                package_unit=observation.package_unit,
                observed_at=observation.observed_at,
                region=observation.region,
            )
            match = match_candidate(food.to_matching_identity(), candidate)
            domains.add(source_domain)
            evidence.append(
                FoodPriceResearchEvidence(
                    observation=observation,
                    source_name=quote.source_name,
                    source_url=source_url,
                    source_domain=source_domain,
                    product_title=quote.product_title,
                    provider_code=observation.provider_code,
                    provider_product_id=observation.provider_product_id,
                    normalized_normal_price_toman=normalized.normalized_normal_price,
                    canonical_unit=normalized.canonical_unit,
                    match_accepted=match.accepted,
                    match_reason_code=match.reason_code,
                    agent_request_id=request_id,
                )
            )

    @staticmethod
    def _has_trusted_initial_cluster(evidence: Sequence[FoodPriceResearchEvidence]) -> bool:
        accepted = [item for item in evidence if item.match_accepted]
        if len({item.source_domain for item in accepted}) < INITIAL_RESEARCH_SOURCES:
            return False
        if len({item.canonical_unit for item in accepted}) != 1:
            return False
        values = [item.normalized_normal_price_toman for item in accepted]
        return len(median_band_indices(values)) == len(values)


__all__ = [
    "AgentFoodPriceResearcher",
    "AgentFoodPriceResearchResult",
    "FOOD_PRICE_RESEARCH_SCHEMA_NAME",
    "FOOD_PRICE_RESEARCH_SYSTEM_PROMPT",
    "FoodPriceResearchError",
    "FoodPriceResearchEvidence",
    "FoodPriceResearchFood",
    "FoodPriceResearchOutput",
    "FoodPriceResearchQuote",
    "MAX_RESEARCH_SOURCES",
    "MEDIAN_BAND_FRACTION",
    "build_food_price_research_request",
    "canonical_source_domain",
    "canonical_source_url",
    "median_band_indices",
]
