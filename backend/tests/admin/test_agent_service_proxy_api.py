import asyncio
import json

import httpx
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.body_analysis.admin_config.models import AIAgentServiceProxySetting, AIAuditEvent

ORIGIN = {"Origin": "http://localhost:5173"}


def _register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201


def _admin(client: TestClient, db: Session) -> User:
    _register(client, "proxy-admin@example.com")
    user = db.scalar(select(User).where(User.email == "proxy-admin@example.com"))
    assert user is not None
    user.is_admin = True
    db.commit()
    return user


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


def _status(source: str = "deployment_default", *, enabled: bool = True) -> dict[str, object]:
    return {
        "enabled": enabled,
        "source": source,
        "configured": source == "custom" or enabled,
        "default_configured": source == "deployment_default",
        "masked_proxy_url": "http://default-proxy:1080"
        if source == "deployment_default"
        else "http://****:****@custom-proxy:8080",
    }


def test_agent_service_proxy_is_admin_only_and_requires_trusted_origin_for_writes(
    client: TestClient,
    db: Session,
) -> None:
    assert client.get("/api/v1/admin/ai/agent-service/proxy").status_code == 401
    _register(client, "proxy-member@example.com")
    assert client.get("/api/v1/admin/ai/agent-service/proxy").status_code == 403
    _admin(client, db)

    response = client.put(
        "/api/v1/admin/ai/agent-service/proxy",
        json={"enabled": False, "source": "deployment_default"},
    )
    assert response.status_code == 403


def test_agent_service_proxy_defaults_to_deployment_proxy(
    client: TestClient, db: Session, test_settings
) -> None:
    _admin(client, db)
    test_settings.agent_service_token = SecretStr("t" * 32)

    replacement = _mock_agent_service(
        client,
        httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=_status(),
                request=request,
            )
        ),
    )
    try:
        response = client.get("/api/v1/admin/ai/agent-service/proxy")
    finally:
        _restore_agent_service(client, replacement)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "enabled": True,
        "source": "deployment_default",
        "configured": True,
        "default_configured": True,
        "masked_proxy_url": "http://default-proxy:1080",
        "applied": True,
        "agent_service_available": True,
        "last_applied_at": None,
        "last_apply_error": None,
    }


def test_admin_saves_encrypted_custom_proxy_and_applies_it_without_leaking_secret(
    client: TestClient,
    db: Session,
    test_settings,
) -> None:
    admin = _admin(client, db)
    test_settings.agent_service_token = SecretStr("t" * 32)
    test_settings.ai_credential_encryption_key = Fernet.generate_key().decode()
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.method == "PUT"
        assert request.url.path == "/v1/runtime/proxy"
        assert request.headers["authorization"] == f"Bearer {'t' * 32}"
        body = json.loads(request.content)
        assert body == {
            "enabled": True,
            "source": "custom",
            "proxy_url": "http://admin:secret@custom-proxy:8080",
        }
        return httpx.Response(200, json=_status("custom"), request=request)

    replacement = _mock_agent_service(client, httpx.MockTransport(handler))
    try:
        response = client.put(
            "/api/v1/admin/ai/agent-service/proxy",
            headers=ORIGIN,
            json={
                "enabled": True,
                "source": "custom",
                "proxy_url": "http://admin:secret@custom-proxy:8080",
            },
        )
    finally:
        _restore_agent_service(client, replacement)

    assert response.status_code == 200, response.text
    assert response.json()["masked_proxy_url"] == "http://****:****@custom-proxy:8080"
    assert "admin:secret" not in response.text
    record = db.scalar(select(AIAgentServiceProxySetting))
    assert record is not None
    assert record.enabled is True
    assert record.source == "custom"
    assert record.encrypted_proxy_url != "http://admin:secret@custom-proxy:8080"
    assert record.masked_proxy_url == "http://****:****@custom-proxy:8080"
    assert record.updated_by_user_id == admin.id
    audit = db.scalar(select(AIAuditEvent).order_by(AIAuditEvent.created_at.desc()))
    assert audit is not None
    assert "http://admin:secret" not in json.dumps(audit.changed_fields)
    assert "secret" not in json.dumps(audit.changed_fields)
    assert calls


def test_admin_can_disable_proxy_without_deleting_saved_custom_value(
    client: TestClient,
    db: Session,
    test_settings,
) -> None:
    _admin(client, db)
    test_settings.agent_service_token = SecretStr("t" * 32)
    test_settings.ai_credential_encryption_key = Fernet.generate_key().decode()
    responses = iter([_status("custom"), _status("custom", enabled=False)])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=next(responses), request=request)

    replacement = _mock_agent_service(client, httpx.MockTransport(handler))
    try:
        saved = client.put(
            "/api/v1/admin/ai/agent-service/proxy",
            headers=ORIGIN,
            json={
                "enabled": True,
                "source": "custom",
                "proxy_url": "http://admin:secret@custom-proxy:8080",
            },
        )
        disabled = client.put(
            "/api/v1/admin/ai/agent-service/proxy",
            headers=ORIGIN,
            json={"enabled": False, "source": "custom"},
        )
    finally:
        _restore_agent_service(client, replacement)

    assert saved.status_code == 200, saved.text
    assert disabled.status_code == 200, disabled.text
    record = db.scalar(select(AIAgentServiceProxySetting))
    assert record is not None
    assert record.enabled is False
    assert record.source == "custom"
    assert record.encrypted_proxy_url is not None


def test_custom_proxy_url_is_validated_before_agent_service_call(
    client: TestClient,
    db: Session,
    test_settings,
) -> None:
    _admin(client, db)
    test_settings.agent_service_token = SecretStr("t" * 32)
    test_settings.ai_credential_encryption_key = Fernet.generate_key().decode()
    replacement = _mock_agent_service(
        client,
        httpx.MockTransport(
            lambda request: (_ for _ in ()).throw(AssertionError(f"unexpected call: {request}"))
        ),
    )
    try:
        response = client.put(
            "/api/v1/admin/ai/agent-service/proxy",
            headers=ORIGIN,
            json={"enabled": True, "source": "custom", "proxy_url": "not-a-proxy"},
        )
    finally:
        _restore_agent_service(client, replacement)

    assert response.status_code == 422
    assert "proxy" in response.text.lower()
