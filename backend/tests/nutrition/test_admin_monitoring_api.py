from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from tests.nutrition.test_weekly_plan_api import ORIGIN


def test_admin_monitoring_requires_admin_and_reports_catalogues(
    client: TestClient, db: Session
) -> None:
    assert (
        client.post(
            "/api/v1/auth/register",
            headers=ORIGIN,
            json={"email": "monitor@example.com", "password": "long password"},
        ).status_code
        == 201
    )
    assert client.get("/api/v1/nutrition/admin/monitoring").status_code == 403
    user = db.scalar(select(User).where(User.email == "monitor@example.com"))
    assert user is not None
    user.is_admin = True
    db.flush()

    response = client.get("/api/v1/nutrition/admin/monitoring")

    assert response.status_code == 200
    assert set(response.json()["counts"]) == {
        "foods",
        "meals",
        "accepted_price_references",
        "price_reviews",
        "supplements",
    }
    assert isinstance(response.json()["recent_price_runs"], list)
    assert isinstance(response.json()["provider_health"], list)
    assert response.json()["ai_usage"] == {
        "requests": 0,
        "errors": 0,
        "input_tokens": 0,
        "output_tokens": 0,
    }
    assert len(response.json()["provider_health"]) == 11
    assert all("api_key" not in provider for provider in response.json()["provider_health"])
    assert "coverage_warning" in response.json()
    assert "price_reviews" in response.json()
    assert "broken_mappings" in response.json()


def test_admin_can_trigger_manual_price_update_without_live_credentials(
    client: TestClient, db: Session, monkeypatch
) -> None:
    from app.nutrition import router as nutrition_router

    assert (
        client.post(
            "/api/v1/auth/register",
            headers=ORIGIN,
            json={"email": "price-admin@example.com", "password": "long password"},
        ).status_code
        == 201
    )
    assert client.post("/api/v1/nutrition/admin/prices/refresh", headers=ORIGIN).status_code == 403
    user = db.scalar(select(User).where(User.email == "price-admin@example.com"))
    assert user is not None
    user.is_admin = True
    db.flush()
    monkeypatch.setattr(nutrition_router, "configured_providers", lambda _settings, _client: [])

    response = client.post("/api/v1/nutrition/admin/prices/refresh", headers=ORIGIN)

    assert response.status_code == 200
    assert response.json()["trigger_kind"] == "manual"
    assert response.json()["status"] == "completed_with_errors"
    assert "NO_PROVIDERS" in response.json()["failure_codes"]


def test_admin_manual_price_refresh_passes_resolved_agent_execution(
    client: TestClient, db: Session, monkeypatch
) -> None:
    from types import SimpleNamespace
    from uuid import uuid4

    from app.nutrition import router as nutrition_router
    from app.nutrition.enums import PriceUpdateRunStatus, PriceUpdateTriggerKind
    from app.nutrition.price_execution import PriceUpdateExecution

    assert (
        client.post(
            "/api/v1/auth/register",
            headers=ORIGIN,
            json={"email": "agent-price-admin@example.com", "password": "long password"},
        ).status_code
        == 201
    )
    user = db.scalar(select(User).where(User.email == "agent-price-admin@example.com"))
    assert user is not None
    user.is_admin = True
    db.flush()
    marker = object()
    captured: dict[str, object] = {}

    def resolve(_db, **kwargs):
        captured["agent_client"] = kwargs["agent_http_client"]
        return PriceUpdateExecution(providers=(), agent_researcher=marker)  # type: ignore[arg-type]

    async def update(_db, **kwargs):
        captured["providers"] = kwargs["providers"]
        captured["agent_researcher"] = kwargs["agent_researcher"]
        return SimpleNamespace(
            id=uuid4(),
            status=PriceUpdateRunStatus.COMPLETED,
            trigger_kind=PriceUpdateTriggerKind.MANUAL,
            started_at=None,
            finished_at=None,
            foods_attempted=1,
            foods_updated=1,
            foods_needing_review=0,
            provider_failures=0,
            failure_codes=[],
        )

    monkeypatch.setattr(nutrition_router, "resolve_price_update_execution", resolve, raising=False)
    monkeypatch.setattr(nutrition_router, "run_price_update_async", update)

    response = client.post("/api/v1/nutrition/admin/prices/refresh", headers=ORIGIN)

    assert response.status_code == 200, response.text
    assert captured["providers"] == ()
    assert captured["agent_researcher"] is marker
    assert captured["agent_client"] is not None


def test_monitoring_returns_only_quote_evidence_referenced_by_review(
    client: TestClient, db: Session
) -> None:
    from datetime import UTC, date, datetime
    from decimal import Decimal

    from app.nutrition.enums import (
        FoodVerificationStatus,
        PriceProviderKind,
        PriceQuoteStatus,
        PriceUpdateRunStatus,
        PriceUpdateTriggerKind,
    )
    from app.nutrition.models import (
        NutritionCatalogueFood,
        NutritionFoodPriceQuote,
        NutritionFoodPriceReview,
        NutritionFoodPriceUpdateRun,
        NutritionPriceProvider,
    )

    food = NutritionCatalogueFood(
        slug="monitor-agent-rice",
        name_fa="برنج ایرانی",
        name_en="Iranian rice",
        category="grains",
        verification_status=FoodVerificationStatus.VERIFIED,
        source_name="test",
        source_reference="test",
    )
    other_food = NutritionCatalogueFood(
        slug="monitor-unrelated-food",
        name_fa="غذای دیگر",
        name_en="Other food",
        category="other",
        verification_status=FoodVerificationStatus.VERIFIED,
        source_name="test",
        source_reference="test",
    )
    provider = NutritionPriceProvider(
        code="agent_web_monitoring",
        kind=PriceProviderKind.PUBLIC_CATALOG,
        name="monitor.example",
        enabled=True,
        base_url="https://monitor.example/",
        parser_version="agent-web-v1",
    )
    now = datetime(2026, 8, 10, 12, tzinfo=UTC)
    run = NutritionFoodPriceUpdateRun(
        scheduled_for=now,
        started_at=now,
        finished_at=now,
        status=PriceUpdateRunStatus.COMPLETED_WITH_ERRORS,
        trigger_kind=PriceUpdateTriggerKind.MANUAL,
        policy_version="public-price-v3",
    )
    db.add_all([food, other_food, provider, run])
    db.flush()

    def quote_row(
        food_id, product_id: str, source_url: str, normal: int, promo: int | None
    ) -> NutritionFoodPriceQuote:
        return NutritionFoodPriceQuote(
            food_id=food_id,
            provider_code=provider.code,
            provider_product_id=product_id,
            provider_observation_key=product_id,
            package_quantity=Decimal("1"),
            package_unit="kg",
            normal_price_irr=Decimal(normal * 10),
            promotional_price_irr=Decimal(promo * 10) if promo is not None else None,
            normalized_normal_irr=Decimal(normal * 10),
            normalized_promotional_irr=Decimal(promo * 10) if promo is not None else None,
            observed_at=now,
            fetched_at=now,
            effective_date=date(2026, 8, 10),
            parser_version="agent-web-v1",
            status=PriceQuoteStatus.FRESH,
            raw_quote={
                "title": "برنج ایرانی 1 کیلوگرم",
                "region": "تهران",
                "currency": "TOMAN",
                "source_name": "Monitor Shop",
                "source_url": source_url,
                "source_domain": "monitor.example",
                "research_backend": "agent_service",
                "agent_request_id": "agent-request-1",
            },
        )

    referenced_one = quote_row(
        food.id, "referenced-one", "https://monitor.example/one", 190000, 180000
    )
    referenced_two = quote_row(
        food.id, "referenced-two", "https://monitor.example/two", 198000, None
    )
    unrelated = quote_row(
        other_food.id, "unrelated", "https://monitor.example/unrelated", 999000, None
    )
    db.add_all([referenced_one, referenced_two, unrelated])
    db.flush()
    db.add(
        NutritionFoodPriceReview(
            run_id=run.id,
            food_id=food.id,
            reason_codes=["source_disagreement"],
            candidate_reference_price_toman=Decimal("194000"),
            source_quote_ids=[str(referenced_one.id), str(referenced_two.id)],
            created_at=now,
        )
    )
    db.commit()

    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": "monitor-evidence-admin@example.com", "password": "long password"},
    )
    assert response.status_code == 201
    user = db.scalar(select(User).where(User.email == "monitor-evidence-admin@example.com"))
    assert user is not None
    user.is_admin = True
    db.commit()

    monitoring = client.get("/api/v1/nutrition/admin/monitoring")

    assert monitoring.status_code == 200, monitoring.text
    review = next(
        item for item in monitoring.json()["price_reviews"] if item["food_slug"] == food.slug
    )
    assert review["reason_codes"] == ["source_disagreement"]
    assert review["candidate_reference_price_toman"] == "194000"
    assert [item["source_url"] for item in review["quotes"]] == [
        "https://monitor.example/one",
        "https://monitor.example/two",
    ]
    assert review["quotes"][0]["source_domain"] == "monitor.example"
    assert review["quotes"][0]["source_name"] == "Monitor Shop"
    assert review["quotes"][0]["normal_price_toman"] == "190000"
    assert review["quotes"][0]["promotional_price_toman"] == "180000"
    assert review["quotes"][0]["normalized_normal_price_toman"] == "190000"
    assert review["quotes"][0]["package_quantity"] == "1"
    assert review["quotes"][0]["package_unit"] == "kg"
    assert review["quotes"][0]["product_title"] == "برنج ایرانی 1 کیلوگرم"
    assert "unrelated" not in monitoring.text
