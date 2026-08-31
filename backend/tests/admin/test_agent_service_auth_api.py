import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.config import Settings

ORIGIN = {"Origin": "http://localhost:5173"}
TOKEN = "agent-service-test-token-with-32-bytes-123"


def _register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201


def _admin(client: TestClient, db: Session, email: str = "agent-auth-admin@example.com") -> None:
    _register(client, email)
    user = db.scalar(select(User).where(User.email == email))
    assert user is not None
    user.is_admin = True
    db.commit()


def _mock_agent_service(client: TestClient, handler: httpx.MockTransport) -> httpx.AsyncClient:
    original = client.app.state.agent_http_client
    replacement = httpx.AsyncClient(transport=handler)
    client.app.state.agent_http_client = replacement
    client.app.state._test_original_agent_http_client = original
    return replacement


def _restore_agent_service(client: TestClient, replacement: httpx.AsyncClient) -> None:
    client.app.state.agent_http_client = client.app.state._test_original_agent_http_client
    del client.app.state._test_original_agent_http_client
    asyncio.run(replacement.aclose())


def _session_payload(session_id: str, *, status: str = "waiting_for_user") -> dict[str, object]:
    return {
        "session_id": session_id,
        "agent": "codex",
        "status": status,
        "verification_url": "https://auth.openai.com/device?state=opaque",
        "user_code": "ABCD-EFGH",
        "input_label": None,
        "expires_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        "safe_error_message": None,
    }


def test_agent_auth_routes_proxy_through_backend_and_require_admin_origin(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    start_path = "/api/v1/admin/ai/agent-service/auth/start"
    assert client.post(start_path, json={"agent": "codex"}).status_code == 401
    _register(client, "agent-auth-member@example.com")
    assert client.post(start_path, json={"agent": "codex"}).status_code == 403
    _admin(client, db)
    test_settings.agent_service_token = TOKEN

    session_id = str(uuid4())
    seen: list[tuple[str, str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            (request.method, request.url.path, request.content and request.content.decode())
        )
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        if request.method == "POST" and request.url.path.endswith("/start"):
            return httpx.Response(200, json=_session_payload(session_id))
        if request.method == "GET":
            return httpx.Response(
                200,
                json=_session_payload(session_id, status="waiting_for_input"),
            )
        if request.method == "POST" and request.url.path.endswith("/input"):
            return httpx.Response(200, json=_session_payload(session_id, status="verifying"))
        if request.method == "DELETE":
            return httpx.Response(200, json=_session_payload(session_id, status="canceled"))
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    replacement = _mock_agent_service(client, httpx.MockTransport(handler))
    try:
        without_origin = client.post(start_path, json={"agent": "codex"})
        started = client.post(start_path, headers=ORIGIN, json={"agent": "codex"})
        current = client.get(
            f"/api/v1/admin/ai/agent-service/auth/{session_id}",
        )
        submitted = client.post(
            f"/api/v1/admin/ai/agent-service/auth/{session_id}/input",
            headers=ORIGIN,
            json={"value": "authorization-code"},
        )
        canceled = client.delete(
            f"/api/v1/admin/ai/agent-service/auth/{session_id}",
            headers=ORIGIN,
        )
    finally:
        _restore_agent_service(client, replacement)

    assert without_origin.status_code == 403
    assert started.status_code == 200, started.text
    assert current.status_code == 200, current.text
    assert submitted.status_code == 200, submitted.text
    assert canceled.status_code == 200, canceled.text
    assert all(
        "token" not in response.text.lower()
        for response in (started, current, submitted, canceled)
    )
    assert [method for method, _path, _body in seen] == ["POST", "GET", "POST", "DELETE"]


def test_agent_auth_proxy_accepts_antigravity_google_oauth_url(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    _admin(client, db)
    test_settings.agent_service_token = TOKEN
    session_id = str(uuid4())
    payload = _session_payload(session_id, status="waiting_for_input")
    payload.update(
        {
            "agent": "antigravity",
            "verification_url": "https://accounts.google.com/o/oauth2/auth?state=opaque",
            "user_code": None,
            "input_label": "authorization code",
        }
    )
    replacement = _mock_agent_service(
        client,
        httpx.MockTransport(lambda _request: httpx.Response(200, json=payload)),
    )
    try:
        response = client.post(
            "/api/v1/admin/ai/agent-service/auth/start",
            headers=ORIGIN,
            json={"agent": "antigravity"},
        )
    finally:
        _restore_agent_service(client, replacement)

    assert response.status_code == 200, response.text
    assert response.json()["agent"] == "antigravity"
    assert response.json()["verification_url"].startswith("https://accounts.google.com/")
    assert response.json()["input_label"] == "authorization code"


def test_cancel_active_agent_auth_proxy_is_admin_origin_protected_and_safe(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    path = "/api/v1/admin/ai/agent-service/auth/cancel-active"
    assert client.post(path, json={"agent": "codex"}).status_code == 401
    _register(client, "cancel-active-member@example.com")
    assert client.post(path, json={"agent": "codex"}).status_code == 403
    _admin(client, db, "cancel-active-admin@example.com")
    test_settings.agent_service_token = TOKEN
    seen: list[tuple[str, str, bytes]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path, request.content))
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        assert request.method == "POST"
        assert request.url.path.endswith("/v1/auth/cancel-active")
        assert request.content == b'{"agent":"codex"}'
        canceled = len(seen) == 1
        return httpx.Response(200, json={"agent": "codex", "canceled": canceled})

    replacement = _mock_agent_service(client, httpx.MockTransport(handler))
    try:
        without_origin = client.post(path, json={"agent": "codex"})
        canceled = client.post(path, headers=ORIGIN, json={"agent": "codex"})
        repeated = client.post(path, headers=ORIGIN, json={"agent": "codex"})
    finally:
        _restore_agent_service(client, replacement)

    assert without_origin.status_code == 403
    assert canceled.status_code == 200
    assert canceled.json() == {"agent": "codex", "canceled": True}
    assert repeated.status_code == 200
    assert repeated.json() == {"agent": "codex", "canceled": False}
    assert [method for method, _path, _body in seen] == ["POST", "POST"]
    assert "9001" not in canceled.text
    assert "token" not in canceled.text.lower()


def test_agent_auth_proxy_maps_safe_downstream_errors_without_internal_details(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    _admin(client, db)
    test_settings.agent_service_token = TOKEN
    replacement = _mock_agent_service(
        client,
        httpx.MockTransport(
            lambda _request: httpx.Response(
                409,
                json={
                    "error": {
                        "code": "auth_in_progress",
                        "message": "private credential detail",
                        "request_id": "private-request-id",
                    }
                },
            )
        ),
    )
    try:
        response = client.post(
            "/api/v1/admin/ai/agent-service/auth/start",
            headers=ORIGIN,
            json={"agent": "codex"},
        )
    finally:
        _restore_agent_service(client, replacement)

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "auth_in_progress",
        "message": "Authentication is already in progress.",
    }
    assert "private" not in response.text
    assert "token" not in response.text.lower()


def test_agent_auth_proxy_rejects_extra_sensitive_response_fields(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    _admin(client, db)
    test_settings.agent_service_token = TOKEN
    payload = _session_payload(str(uuid4()))
    payload["token"] = "secret-token"
    replacement = _mock_agent_service(
        client,
        httpx.MockTransport(lambda _request: httpx.Response(200, json=payload)),
    )
    try:
        response = client.post(
            "/api/v1/admin/ai/agent-service/auth/start",
            headers=ORIGIN,
            json={"agent": "codex"},
        )
    finally:
        _restore_agent_service(client, replacement)

    assert response.status_code == 502
    assert response.json()["detail"] == {
        "code": "malformed_response",
        "message": "The Agent Service returned a malformed response.",
    }
    assert "secret-token" not in response.text
