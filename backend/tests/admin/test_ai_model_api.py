import asyncio

import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.models import AiModel, BillingClass, ZenApiKind
from app.auth.models import User
from app.config import Settings

ORIGIN = {"Origin": "http://localhost:5173"}


def _register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201


def _make_current_user_admin(client: TestClient, db: Session) -> User:
    _register(client, "admin-ai@example.com")
    user = db.scalar(select(User).where(User.email == "admin-ai@example.com"))
    assert user is not None
    user.is_admin = True
    db.commit()
    return user


def _custom_model(db: Session, *, is_enabled: bool = True) -> AiModel:
    model = AiModel(
        model_id="custom-workout-model",
        display_name="Custom workout model",
        api_kind=ZenApiKind.CHAT_COMPLETIONS,
        billing_class=BillingClass.FREE,
        is_enabled=is_enabled,
        priority=50,
        is_custom=True,
        classification_required=False,
    )
    db.add(model)
    db.commit()
    return model


def test_ai_model_routes_require_administrator_access(client: TestClient) -> None:
    assert client.get("/api/v1/admin/ai-models").status_code == 401
    assert (
        client.patch(
            "/api/v1/admin/ai-routing",
            headers=ORIGIN,
            json={"mode": "automatic"},
        ).status_code
        == 401
    )

    _register(client, "member-ai@example.com")

    assert client.get("/api/v1/admin/ai-models").status_code == 403


def test_admin_can_manage_model_and_automatic_routing(client: TestClient, db: Session) -> None:
    _make_current_user_admin(client, db)
    model = _custom_model(db)

    listed = client.get("/api/v1/admin/ai-models")

    assert listed.status_code == 200
    assert "opencode_zen_api_key" not in listed.text
    assert any(item["id"] == str(model.id) for item in listed.json()["models"])

    updated = client.patch(
        f"/api/v1/admin/ai-models/{model.id}",
        headers=ORIGIN,
        json={"display_name": "Renamed model", "priority": 4},
    )
    routing = client.patch(
        "/api/v1/admin/ai-routing",
        headers=ORIGIN,
        json={"mode": "automatic"},
    )

    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Renamed model"
    assert routing.status_code == 200
    assert routing.json()["mode"] == "automatic"


def test_admin_can_create_a_classified_custom_model(client: TestClient, db: Session) -> None:
    _make_current_user_admin(client, db)

    response = client.post(
        "/api/v1/admin/ai-models",
        headers=ORIGIN,
        json={
            "model_id": "new-free-zen-model",
            "display_name": "New Free Zen Model",
            "api_kind": "messages",
            "billing_class": "free",
            "priority": 12,
        },
    )

    assert response.status_code == 201
    assert response.json()["is_custom"] is True
    assert response.json()["classification_required"] is False


def test_admin_rejects_manual_selection_of_a_disabled_model(
    client: TestClient,
    db: Session,
) -> None:
    _make_current_user_admin(client, db)
    model = _custom_model(db, is_enabled=False)

    response = client.patch(
        "/api/v1/admin/ai-routing",
        headers=ORIGIN,
        json={"mode": "manual", "manual_model_id": str(model.id)},
    )

    assert response.status_code == 422


def test_sync_marks_unknown_model_for_classification(client: TestClient, db: Session) -> None:
    _make_current_user_admin(client, db)
    original_client = client.app.state.zen_http_client
    mock_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"object": "list", "data": [{"id": "future-zen-model"}]},
            )
        )
    )
    client.app.state.zen_http_client = mock_client
    try:
        response = client.post("/api/v1/admin/ai-models/sync", headers=ORIGIN)
    finally:
        asyncio.run(mock_client.aclose())
        client.app.state.zen_http_client = original_client

    assert response.status_code == 200
    assert response.json()["needs_classification"] == ["future-zen-model"]
    unknown = db.scalar(select(AiModel).where(AiModel.model_id == "future-zen-model"))
    assert unknown is not None
    assert unknown.is_enabled is False
    assert unknown.classification_required is True


def test_admin_can_run_a_model_health_check(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    _make_current_user_admin(client, db)
    model = _custom_model(db)
    test_settings.opencode_zen_api_key = SecretStr("test-key")
    original_client = client.app.state.zen_http_client
    mock_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "id": "health-check",
                    "choices": [{"message": {"content": '{"days": []}'}}],
                },
            )
        )
    )
    client.app.state.zen_http_client = mock_client
    try:
        response = client.post(f"/api/v1/admin/ai-models/{model.id}/test", headers=ORIGIN)
    finally:
        asyncio.run(mock_client.aclose())
        client.app.state.zen_http_client = original_client

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert db.get(AiModel, model.id).last_checked_at is not None  # type: ignore[union-attr]
