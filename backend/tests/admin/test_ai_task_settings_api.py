import asyncio
import json

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.body_analysis.admin_config.models import AIAuditEvent, AIProviderCredential
from app.body_analysis.admin_config.schemas import AITaskConfigUpdate
from app.config import Settings
from app.main import create_app

ORIGIN = {"Origin": "http://localhost:5173"}


def test_task_config_rejects_unsupported_routing_policy() -> None:
    with pytest.raises(ValidationError, match="routing_restrictions"):
        AITaskConfigUpdate.model_validate({"routing_restrictions": ["unsafe_free_text"]})


def _register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201


def _admin(client: TestClient, db: Session) -> User:
    _register(client, "task-ai-admin@example.com")
    user = db.scalar(select(User).where(User.email == "task-ai-admin@example.com"))
    assert user is not None
    user.is_admin = True
    db.commit()
    return user


def _mock_openrouter(client: TestClient, handler: httpx.MockTransport) -> httpx.AsyncClient:
    original = client.app.state.ai_http_client
    replacement = httpx.AsyncClient(transport=handler)
    client.app.state.ai_http_client = replacement
    client.app.state._test_original_ai_http_client = original
    return replacement


def _restore_openrouter(client: TestClient, replacement: httpx.AsyncClient) -> None:
    client.app.state.ai_http_client = client.app.state._test_original_ai_http_client
    del client.app.state._test_original_ai_http_client
    asyncio.run(replacement.aclose())


def _catalog_response(request: httpx.Request) -> httpx.Response:
    assert request.headers["authorization"] == "Bearer sk-openrouter-secret"
    if request.url.path.endswith("/auth/key"):
        return httpx.Response(200, json={"data": {"label": "Fitsho"}})
    return httpx.Response(
        200,
        json={
            "data": [
                {
                    "id": "vendor/text-model",
                    "name": "Text Model",
                    "architecture": {"input_modalities": ["text"]},
                    "supported_parameters": ["response_format"],
                    "context_length": 32000,
                    "pricing": {"prompt": "0.000001", "completion": "0.000002"},
                },
                {
                    "id": "vendor/vision-model",
                    "name": "Vision Model",
                    "architecture": {"input_modalities": ["text", "image"]},
                    "supported_parameters": ["structured_outputs"],
                    "context_length": 64000,
                    "pricing": {"prompt": "0.000003", "completion": "0.000004"},
                },
            ]
        },
    )


def test_task_settings_require_admin_and_trusted_origin(client: TestClient) -> None:
    assert client.get("/api/v1/admin/ai/task-configs").status_code == 401
    _register(client, "task-ai-member@example.com")
    assert client.get("/api/v1/admin/ai/task-configs").status_code == 403
    assert (
        client.put(
            "/api/v1/admin/ai/task-configs/body_photo_analysis",
            json={"provider": "openrouter", "enabled": False},
        ).status_code
        == 403
    )


def test_openrouter_client_is_independent_from_zen_client(test_settings: Settings) -> None:
    test_settings.opencode_zen_proxy_url = "http://127.0.0.1:19876"
    with TestClient(create_app(test_settings)) as app_client:
        assert app_client.app.state.ai_http_client is not app_client.app.state.zen_http_client
        assert app_client.app.state.ai_http_client._trust_env is False


def test_admin_saves_encrypted_masked_credential_and_audits_without_secret(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    admin = _admin(client, db)
    test_settings.ai_credential_encryption_key = Fernet.generate_key().decode()

    response = client.put(
        "/api/v1/admin/ai/task-configs/body_photo_analysis",
        headers=ORIGIN,
        json={
            "provider": "openrouter",
            "enabled": False,
            "api_key": "sk-openrouter-secret",
            "replace_credential": True,
            "temperature": 0.1,
            "max_output_tokens": 4096,
            "timeout_seconds": 45,
            "minimum_confidence": 0.72,
            "max_cost_per_request": "0.15",
                "routing_restrictions": [
                    "deny_provider_data_collection",
                    "zero_data_retention",
                ],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["credential"] == {"configured": True, "masked": "••••cret"}
    assert "sk-openrouter-secret" not in response.text
    credential = db.scalar(select(AIProviderCredential))
    assert credential is not None
    assert "sk-openrouter-secret" not in credential.encrypted_api_key
    assert credential.updated_by_user_id == admin.id
    audit = db.scalar(select(AIAuditEvent).order_by(AIAuditEvent.created_at.desc()))
    assert audit is not None
    assert "api_key" not in json.dumps(audit.changed_fields)
    assert "secret" not in json.dumps(audit.changed_fields)


def test_credential_replacement_must_be_explicit(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    _admin(client, db)
    test_settings.ai_credential_encryption_key = Fernet.generate_key().decode()
    payload = {
        "provider": "openrouter",
        "enabled": False,
        "api_key": "sk-openrouter-secret",
        "replace_credential": False,
    }
    response = client.put(
        "/api/v1/admin/ai/task-configs/workout_plan_generation",
        headers=ORIGIN,
        json=payload,
    )
    assert response.status_code == 422
    assert "explicit" in response.text.lower()


def test_refresh_catalog_and_filter_models_by_task_capability(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    _admin(client, db)
    test_settings.ai_credential_encryption_key = Fernet.generate_key().decode()
    client.put(
        "/api/v1/admin/ai/task-configs/body_photo_analysis",
        headers=ORIGIN,
        json={
            "provider": "openrouter",
            "enabled": False,
            "api_key": "sk-openrouter-secret",
            "replace_credential": True,
        },
    )
    replacement = _mock_openrouter(client, httpx.MockTransport(_catalog_response))
    try:
        refreshed = client.post("/api/v1/admin/ai/models/refresh", headers=ORIGIN)
        vision = client.get("/api/v1/admin/ai/models?task_type=body_photo_analysis&search=vision")
        workout = client.get("/api/v1/admin/ai/models?task_type=workout_plan_generation")
    finally:
        _restore_openrouter(client, replacement)

    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["model_count"] == 2
    assert [item["model_id"] for item in vision.json()["items"]] == ["vendor/vision-model"]
    assert vision.json()["stale"] is False
    assert {item["model_id"] for item in workout.json()["items"]} == {
        "vendor/text-model",
        "vendor/vision-model",
    }
    assert all("api_key" not in item for item in workout.json()["items"])


def test_connection_uses_stored_key_and_returns_only_safe_error(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    _admin(client, db)
    test_settings.ai_credential_encryption_key = Fernet.generate_key().decode()
    client.put(
        "/api/v1/admin/ai/task-configs/progress_comparison",
        headers=ORIGIN,
        json={
            "provider": "openrouter",
            "enabled": False,
            "api_key": "sk-openrouter-secret",
            "replace_credential": True,
        },
    )
    replacement = _mock_openrouter(
        client,
        httpx.MockTransport(
            lambda _request: httpx.Response(401, json={"error": {"message": "secret leaked"}})
        ),
    )
    try:
        response = client.post(
            "/api/v1/admin/ai/providers/test",
            headers=ORIGIN,
            json={"provider": "openrouter"},
        )
    finally:
        _restore_openrouter(client, replacement)

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["error_code"] == "unauthorized"
    assert "secret leaked" not in response.text
    assert "sk-openrouter-secret" not in response.text


def test_body_analysis_rejects_a_text_only_model_when_enabled(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    _admin(client, db)
    test_settings.ai_credential_encryption_key = Fernet.generate_key().decode()
    client.put(
        "/api/v1/admin/ai/task-configs/body_photo_analysis",
        headers=ORIGIN,
        json={
            "provider": "openrouter",
            "enabled": False,
            "api_key": "sk-openrouter-secret",
            "replace_credential": True,
        },
    )
    replacement = _mock_openrouter(client, httpx.MockTransport(_catalog_response))
    try:
        client.post("/api/v1/admin/ai/models/refresh", headers=ORIGIN)
    finally:
        _restore_openrouter(client, replacement)

    response = client.put(
        "/api/v1/admin/ai/task-configs/body_photo_analysis",
        headers=ORIGIN,
        json={
            "provider": "openrouter",
            "enabled": True,
            "primary_model_id": "vendor/text-model",
        },
    )

    assert response.status_code == 422
    assert "image" in response.text.lower()


def test_selected_models_are_validated_even_when_task_is_disabled(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    _admin(client, db)
    test_settings.ai_credential_encryption_key = Fernet.generate_key().decode()
    client.put(
        "/api/v1/admin/ai/task-configs/body_photo_analysis",
        headers=ORIGIN,
        json={
            "provider": "openrouter",
            "enabled": False,
            "api_key": "sk-openrouter-secret",
            "replace_credential": True,
        },
    )
    replacement = _mock_openrouter(client, httpx.MockTransport(_catalog_response))
    try:
        client.post("/api/v1/admin/ai/models/refresh", headers=ORIGIN)
    finally:
        _restore_openrouter(client, replacement)

    text_only = client.put(
        "/api/v1/admin/ai/task-configs/body_photo_analysis",
        headers=ORIGIN,
        json={
            "provider": "openrouter",
            "enabled": False,
            "primary_model_id": "vendor/text-model",
        },
    )
    missing_fallback = client.put(
        "/api/v1/admin/ai/task-configs/body_photo_analysis",
        headers=ORIGIN,
        json={
            "provider": "openrouter",
            "enabled": False,
            "fallback_model_ids": ["vendor/missing-model"],
        },
    )
    malformed_fallback = client.put(
        "/api/v1/admin/ai/task-configs/body_photo_analysis",
        headers=ORIGIN,
        json={
            "provider": "openrouter",
            "enabled": False,
            "fallback_model_ids": [""],
        },
    )

    assert text_only.status_code == 422
    assert "image" in text_only.text.lower()
    assert missing_fallback.status_code == 422
    assert "catalog" in missing_fallback.text.lower()
    assert malformed_fallback.status_code == 422
