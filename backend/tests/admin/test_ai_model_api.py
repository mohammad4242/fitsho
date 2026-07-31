import asyncio
import json

import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.models import AiModel, BillingClass, ZenApiKind
from app.auth.models import User
from app.config import Settings
from app.workouts.models import WorkoutPlanGeneration
from app.workouts.repository import create_generation, fail_generation

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
    request_bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        request_bodies.append(json.loads(request.read()))
        if len(request_bodies) == 1:
            return httpx.Response(200, json={"id": "health-check"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"status":"ok"}'}}]},
        )

    mock_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    )
    client.app.state.zen_http_client = mock_client
    try:
        response = client.post(f"/api/v1/admin/ai-models/{model.id}/test", headers=ORIGIN)
    finally:
        asyncio.run(mock_client.aclose())
        client.app.state.zen_http_client = original_client

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["test_run"] == {
        "id": response.json()["test_run"]["id"],
        "model_id": "custom-workout-model",
        "outcome": "succeeded",
        "error_code": None,
        "safe_error_message": None,
        "provider_status_code": None,
        "provider_error_type": None,
        "provider_error_message": None,
        "created_at": response.json()["test_run"]["created_at"],
    }
    assert db.get(AiModel, model.id).last_checked_at is not None  # type: ignore[union-attr]
    assert request_bodies[0] == {
        "model": "custom-workout-model",
        "messages": [{"role": "user", "content": "Reply only: OK"}],
        "max_tokens": 1,
    }
    assert request_bodies[1]["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "fitsho_model_test_contract",
            "strict": True,
            "schema": request_bodies[1]["response_format"]["json_schema"]["schema"],
        },
    }
    assert "profile" not in json.dumps(request_bodies)


def test_admin_model_test_requires_compact_structured_output(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    _make_current_user_admin(client, db)
    model = _custom_model(db)
    test_settings.opencode_zen_api_key = SecretStr("test-key")
    original_client = client.app.state.zen_http_client
    requests: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.read()))
        if len(requests) == 1:
            return httpx.Response(200, json={"id": "available"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"status":"no"}'}}]},
        )

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client.app.state.zen_http_client = mock_client
    try:
        response = client.post(f"/api/v1/admin/ai-models/{model.id}/test", headers=ORIGIN)
    finally:
        asyncio.run(mock_client.aclose())
        client.app.state.zen_http_client = original_client

    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["test_run"]["error_code"] == "invalid_output"
    assert "structured JSON" in response.json()["test_run"]["safe_error_message"]
    assert len(requests) == 2
    assert "profile" not in json.dumps(requests)
    assert "allowed_exercises" not in json.dumps(requests)


def test_admin_retains_successful_and_failed_model_test_runs(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    _make_current_user_admin(client, db)
    model = _custom_model(db)
    test_settings.opencode_zen_api_key = SecretStr("test-key")
    original_client = client.app.state.zen_http_client
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls in {1, 3}:
            return httpx.Response(200, json={"id": "available"})
        if calls == 2:
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": '{"status":"ok"}'}}]},
            )
        return httpx.Response(
            200,
            json={"error": {"type": "server_error", "message": "upstream failed"}},
        )

    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client.app.state.zen_http_client = mock_client
    try:
        successful = client.post(f"/api/v1/admin/ai-models/{model.id}/test", headers=ORIGIN)
        failed = client.post(f"/api/v1/admin/ai-models/{model.id}/test", headers=ORIGIN)
        history = client.get("/api/v1/admin/ai-model-test-runs?limit=20")
    finally:
        asyncio.run(mock_client.aclose())
        client.app.state.zen_http_client = original_client

    assert successful.json()["success"] is True
    assert successful.json()["test_run"]["outcome"] == "succeeded"
    assert failed.json()["success"] is False
    assert failed.json()["test_run"]["outcome"] == "failed"
    assert failed.json()["test_run"]["error_code"] == "provider_unavailable"
    assert history.status_code == 200
    assert [item["outcome"] for item in history.json()] == ["failed", "succeeded"]
    assert "user_id" not in history.text
    assert "Reply only: OK" not in history.text


def test_admin_can_read_recent_generation_failures_without_user_data(
    client: TestClient,
    db: Session,
) -> None:
    user = _make_current_user_admin(client, db)
    generation = create_generation(
        db,
        user_id=user.id,
        provider="opencode_zen",
        model_id="nemotron-3-ultra-free",
        candidate_count=12,
    )
    diagnostics: list[dict[str, object]] = [
        {
            "model_id": "nemotron-3-ultra-free",
            "phase": "initial",
            "problems": [
                {
                    "code": "duplicate_exercise",
                    "message": "An exercise may not appear twice.",
                    "day_number": 2,
                    "exercise_id": "018f0000-0000-7000-8000-000000000099",
                }
            ],
        }
    ]
    fail_generation(
        db,
        generation,
        error_code="semantic_validation_failed",
        safe_error_message="Workout generation returned an invalid plan.",
        validation_diagnostics=diagnostics,
    )
    db.commit()

    response = client.get("/api/v1/admin/ai-generation-failures?limit=1")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": str(generation.id),
            "model_id": "nemotron-3-ultra-free",
            "created_at": generation.created_at.isoformat().replace("+00:00", "Z"),
            "completed_at": generation.completed_at.isoformat().replace("+00:00", "Z"),  # type: ignore[union-attr]
            "error_code": "semantic_validation_failed",
            "safe_error_message": "Workout generation returned an invalid plan.",
            "validation_diagnostics": diagnostics,
        }
    ]
    assert "user_id" not in response.text
    assert db.get(WorkoutPlanGeneration, generation.id) is generation
