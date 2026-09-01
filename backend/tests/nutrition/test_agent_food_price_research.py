import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from app.body_analysis.providers.models import (
    ModelRoute,
    ProviderRoutingPreferences,
    StructuredGenerationRequest,
    StructuredGenerationResponse,
)
from app.nutrition.ai_price_research import (
    AgentFoodPriceResearcher,
    FoodPriceResearchError,
    FoodPriceResearchFood,
    FoodPriceResearchOutput,
    build_food_price_research_request,
    canonical_source_domain,
)

ROUTE = ModelRoute(primary_model="agent-model")
FOOD = FoodPriceResearchFood(
    slug="chicken-breast",
    name_fa="سینه مرغ",
    name_en="Chicken breast",
    category="protein",
    aliases=("سینه مرغ تازه",),
)


class FakeStructuredProvider:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.payloads = list(payloads)
        self.requests: list[StructuredGenerationRequest] = []

    async def generate_structured_text(
        self, request: StructuredGenerationRequest
    ) -> StructuredGenerationResponse:
        self.requests.append(request)
        if not self.payloads:
            raise AssertionError("unexpected additional Agent request")
        return StructuredGenerationResponse(
            payload=self.payloads.pop(0),
            model_id=request.route.primary_model,
            attempted_models=(request.route.primary_model,),
            provider_request_id=f"agent-request-{len(self.requests)}",
        )


def quote(
    domain: str,
    price: int,
    *,
    url_domain: str | None = None,
    title: str = "سینه مرغ تازه 1 کیلوگرم",
    quantity: str = "1",
    unit: str = "kg",
    currency: str = "TOMAN",
    promotional_price: int | None = None,
) -> dict[str, Any]:
    source_domain = url_domain or domain
    return {
        "source_name": domain,
        "source_url": f"https://{source_domain}/products/chicken-breast",
        "product_title": title,
        "normal_price": price,
        "promotional_price": promotional_price,
        "currency": currency,
        "package_quantity": quantity,
        "package_unit": unit,
        "region": "تهران",
    }


def output(*quotes: dict[str, Any]) -> dict[str, Any]:
    return {"food_slug": FOOD.slug, "quotes": list(quotes)}


def run_research(provider: FakeStructuredProvider):
    return asyncio.run(AgentFoodPriceResearcher(provider, route=ROUTE).research(FOOD))


def test_request_targets_three_sources_and_uses_canonical_prompt() -> None:
    request = build_food_price_research_request(
        FOOD,
        route=ROUTE,
        requested_source_count=3,
        provider_preferences=ProviderRoutingPreferences(),
    )

    assert request.input_payload["task"] == "research_current_iran_food_retail_prices"
    assert request.input_payload["requested_source_count"] == 3
    assert request.input_payload["excluded_domains"] == []
    assert request.input_payload["market"] == "Iran"
    assert "Use live web search/browser tools" in request.system_prompt
    assert "Do not answer from model memory" in request.system_prompt
    assert "Do not calculate the Fitsho reference price" in request.system_prompt
    assert "final average" not in request.system_prompt.lower()
    assert "database ID" not in request.system_prompt
    assert request.schema_name == "fitsho_food_price_research_v1"


def test_output_models_forbid_extra_fields_and_bound_quotes() -> None:
    valid = output(quote("digikala.com", 190000))
    assert FoodPriceResearchOutput.model_validate(valid).food_slug == FOOD.slug

    with pytest.raises(ValueError):
        FoodPriceResearchOutput.model_validate(
            {**valid, "unexpected": True}
        )

    with pytest.raises(ValueError):
        FoodPriceResearchOutput.model_validate(
            output(*[quote(f"shop-{index}.ir", 190000) for index in range(6)])
        )


def test_coherent_three_sources_do_not_cause_a_second_agent_call() -> None:
    provider = FakeStructuredProvider(
        [
            output(
                quote("digikala.com", 190000),
                quote("okala.ir", 198000),
                quote("basalam.com", 205000),
            )
        ]
    )

    result = run_research(provider)

    assert len(provider.requests) == 1
    assert provider.requests[0].input_payload["requested_source_count"] == 3
    assert len(result.evidence) == 3
    assert result.expanded is False


def test_incoherent_first_pass_expands_with_exclusions_and_two_slots() -> None:
    provider = FakeStructuredProvider(
        [
            output(
                quote("digikala.com", 190000),
                quote("okala.ir", 200000),
                quote("basalam.com", 430000),
            ),
            output(quote("torob.com", 195000), quote("emalls.ir", 205000)),
        ]
    )

    result = run_research(provider)

    assert len(provider.requests) == 2
    assert provider.requests[1].input_payload["requested_source_count"] == 2
    assert set(provider.requests[1].input_payload["excluded_domains"]) == {
        "digikala.com",
        "okala.ir",
        "basalam.com",
    }
    assert {item.source_domain for item in result.evidence} == {
        "digikala.com",
        "okala.ir",
        "basalam.com",
        "torob.com",
        "emalls.ir",
    }


def test_same_source_domain_counts_once() -> None:
    provider = FakeStructuredProvider(
        [
            output(
                quote("www.digikala.com", 190000, url_domain="www.digikala.com"),
                quote("digikala.com", 198000),
                quote("okala.ir", 200000),
            ),
            output(quote("basalam.com", 205000)),
        ]
    )

    result = run_research(provider)

    assert len(provider.requests) == 2
    assert len(result.evidence) == 3
    assert [item.source_domain for item in result.evidence].count("digikala.com") == 1


@pytest.mark.parametrize(
    "source_url",
    [
        "http://digikala.com/product",
        "https://localhost/product",
        "https://127.0.0.1/product",
        "https://10.0.0.4/product",
        "https://user:password@digikala.com/product",
        "https:///missing-host",
    ],
)
def test_invalid_source_urls_are_rejected(source_url: str) -> None:
    with pytest.raises(ValueError):
        canonical_source_domain(source_url)


def test_domain_helper_normalizes_www_trailing_dot_and_iranian_suffixes() -> None:
    assert canonical_source_domain("https://www.digikala.com./item") == "digikala.com"
    assert canonical_source_domain("https://shop.example.ir/item") == "example.ir"
    assert canonical_source_domain("https://www.shop.example.co.ir/item") == "example.co.ir"


@pytest.mark.parametrize(
    "changes",
    [
        {"quantity": "0"},
        {"quantity": "-1"},
        {"currency": "USD"},
    ],
)
def test_invalid_quote_shape_becomes_safe_research_failure(changes: dict[str, str]) -> None:
    provider = FakeStructuredProvider([output(quote("digikala.com", 190000, **changes))])

    with pytest.raises(FoodPriceResearchError):
        run_research(provider)


def test_obvious_prepared_product_mismatch_is_not_accepted() -> None:
    provider = FakeStructuredProvider(
        [
            output(
                quote("digikala.com", 190000, title="ساندویچ سینه مرغ آماده"),
                quote("okala.ir", 198000),
                quote("basalam.com", 205000),
            ),
            output(quote("torob.com", 200000)),
        ]
    )

    result = run_research(provider)

    mismatch = next(item for item in result.evidence if item.source_domain == "digikala.com")
    assert mismatch.match_accepted is False


def test_second_response_cannot_push_total_evidence_above_five_domains() -> None:
    provider = FakeStructuredProvider(
        [
            output(
                quote("digikala.com", 190000),
                quote("okala.ir", 350000),
                quote("basalam.com", 520000),
            ),
            output(
                quote("torob.com", 760000),
                quote("emalls.ir", 1100000),
                quote("new-one.ir", 1200000),
                quote("new-two.ir", 1300000),
            ),
        ]
    )

    result = run_research(provider)

    assert len(provider.requests) == 2
    assert provider.requests[1].input_payload["requested_source_count"] == 2
    assert len(result.evidence) == 5


def test_malformed_agent_structured_output_is_safe_failure() -> None:
    provider = FakeStructuredProvider([{"food_slug": FOOD.slug, "quotes": [{"bad": True}]}])

    with pytest.raises(FoodPriceResearchError) as error:
        run_research(provider)

    assert "bad" not in str(error.value)
    assert len(provider.requests) == 1


def test_research_uses_current_date_and_no_user_pii() -> None:
    request = build_food_price_research_request(FOOD, route=ROUTE, requested_source_count=3)

    assert request.input_payload["as_of_date"] == datetime.now(UTC).date().isoformat()
    assert "email" not in repr(request.input_payload).lower()
    assert "password" not in repr(request.input_payload).lower()
