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
