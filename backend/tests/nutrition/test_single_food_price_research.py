import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.body_analysis.providers.models import (
    ModelRoute,
    StructuredGenerationRequest,
    StructuredGenerationResponse,
)
from app.nutrition.ai_price_research import (
    AgentFoodPriceResearcher,
    FoodPriceResearchFood,
)
from app.nutrition.enums import FoodVerificationStatus
from app.nutrition.models import NutritionCatalogueFood, NutritionFoodPriceOverride
from app.profile.enums import ProductMode
from app.profile.models import UserProfile

ORIGIN = {"Origin": "http://localhost:5173"}


def _register_admin(
    client: TestClient, db: Session, email: str = "price-admin@example.com"
) -> User:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password 1234"},
    )
    assert response.status_code == 201
    user = db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.is_admin = True
    db.add(UserProfile(user_id=user.id, product_mode=ProductMode.NUTRITION))
    db.commit()
    return user


def _seed_food(db: Session, slug: str = "test-hashemi-rice") -> NutritionCatalogueFood:
    food = NutritionCatalogueFood(
        slug=slug,
        name_fa="برنج هاشمی",
        name_en="Hashemi Rice",
        category="grains",
        verification_status=FoodVerificationStatus.VERIFIED,
        source_name="test",
        source_reference="https://example.test/rice",
    )
    db.add(food)
    db.commit()
    return food


class FakeStructuredProvider:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.payloads = list(payloads)
        self.requests: list[StructuredGenerationRequest] = []

    async def generate_structured_text(
        self, request: StructuredGenerationRequest
    ) -> StructuredGenerationResponse:
        self.requests.append(request)
        return StructuredGenerationResponse(
            payload=self.payloads.pop(0),
            model_id=request.route.primary_model,
            attempted_models=(request.route.primary_model,),
            provider_request_id=f"agent-req-{len(self.requests)}",
        )


def _quote(domain: str, price: int, *, title: str = "برنج هاشمی 1 کیلوگرم") -> dict[str, Any]:
    return {
        "source_name": domain.split(".")[0].capitalize(),
        "source_url": f"https://{domain}/item-1",
        "product_title": title,
        "normal_price": price,
        "promotional_price": None,
        "currency": "TOMAN",
        "package_quantity": 1,
        "package_unit": "kg",
        "region": "تهران",
    }


def test_research_requires_auth_and_origin(client: TestClient, db: Session) -> None:
    food = _seed_food(db, slug="auth-test-food")
    resp_no_auth = client.post(
        f"/api/v1/nutrition/admin/foods/{food.slug}/price-research", headers=ORIGIN
    )
    assert resp_no_auth.status_code == 401

    _register_admin(client, db, email="admin-origin@example.com")
    resp_no_origin = client.post(f"/api/v1/nutrition/admin/foods/{food.slug}/price-research")
    assert resp_no_origin.status_code == 403


def test_research_food_not_found(client: TestClient, db: Session) -> None:
    _register_admin(client, db, email="admin-404@example.com")
    resp = client.post("/api/v1/nutrition/admin/foods/non-existent/price-research", headers=ORIGIN)
    assert resp.status_code == 404


def test_research_single_food_success_and_apply(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = _register_admin(client, db, email="admin-success@example.com")
    food = _seed_food(db, slug="rice-for-research")

    payload = {
        "food_slug": food.slug,
        "quotes": [
            _quote("store-a.ir", 120000),
            _quote("store-b.ir", 125000),
            _quote("store-c.ir", 122000),
        ],
    }
    fake_provider = FakeStructuredProvider([payload])
    researcher = AgentFoodPriceResearcher(
        fake_provider,  # type: ignore[arg-type]
        route=ModelRoute(primary_model="test-agent"),
    )

    monkeypatch.setattr(
        "app.nutrition.router.resolve_single_food_price_researcher",
        lambda *args, **kwargs: researcher,
    )

    # First test inquiry without apply
    resp = client.post(
        f"/api/v1/nutrition/admin/foods/{food.slug}/price-research",
        headers=ORIGIN,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["food_slug"] == food.slug
    assert data["food_name_fa"] == food.name_fa
    assert data["canonical_unit"] == "TOMAN_PER_KG"
    assert data["candidate_reference_price_toman"] is not None
    assert len(data["quotes"]) == 3
    assert data["quotes"][0]["source_domain"] == "store-a.ir"
    assert data["quotes"][0]["normal_price_toman"] == "120000"

    # Verify no override was created yet
    override_count = db.scalar(
        select(NutritionFoodPriceOverride).where(NutritionFoodPriceOverride.food_id == food.id)
    )
    assert override_count is None

    # Now test with apply=true
    fake_provider.payloads.append(payload)
    resp_applied = client.post(
        f"/api/v1/nutrition/admin/foods/{food.slug}/price-research?apply=true",
        headers=ORIGIN,
    )
    assert resp_applied.status_code == 200
    applied_data = resp_applied.json()
    assert applied_data["status"] == "success"

    # Verify override is now created in db
    override = db.scalar(
        select(NutritionFoodPriceOverride).where(NutritionFoodPriceOverride.food_id == food.id)
    )
    assert override is not None
    assert override.active is True
    assert override.created_by_user_id == admin.id
    assert override.canonical_unit == "TOMAN_PER_KG"


def test_single_food_inquiry_can_stop_after_first_evidence_pass() -> None:
    payload = {
        "food_slug": "rice-for-inquiry",
        "quotes": [_quote("store-a.ir", 120000)],
    }
    fake_provider = FakeStructuredProvider([payload])
    researcher = AgentFoodPriceResearcher(
        fake_provider,  # type: ignore[arg-type]
        route=ModelRoute(primary_model="test-agent"),
    )

    result = asyncio.run(
        researcher.research(
            FoodPriceResearchFood(
                slug="rice-for-inquiry",
                name_fa="برنج هاشمی",
                name_en="Hashemi Rice",
                category="grains",
            ),
            expand_sources=False,
        )
    )

    assert len(fake_provider.requests) == 1
    assert result.expanded is False
    assert len(result.evidence) == 1
