import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.body_analysis.admin_config.enums import AIAgentName, AITaskType
from app.body_analysis.admin_config.models import (
    AIAgentProfileVerification,
    AIAuditEvent,
    AIModelCatalogEntry,
    AIProviderCredential,
)
from app.body_analysis.admin_config.schemas import AITaskConfigUpdate
from app.config import Settings
from app.main import create_app

ORIGIN = {"Origin": "http://localhost:5173"}


def test_ai_task_type_matches_persisted_task_catalog() -> None:
    assert {task.value for task in AITaskType} == {
        "workout_plan_generation",
        "body_photo_analysis",
        "progress_comparison",
        "food_photo_estimation",
        "food_price_search",
    }


def test_task_config_rejects_unsupported_routing_policy() -> None:
    with pytest.raises(ValidationError, match="routing_restrictions"):
        AITaskConfigUpdate.model_validate({"routing_restrictions": ["unsafe_free_text"]})


def test_agent_service_task_config_requires_profile_id_field() -> None:
    payload = AITaskConfigUpdate.model_validate(
        {
            "execution_backend": "agent_service",
            "agent_name": "codex",
            "agent_profile_id": "codex-gpt-5.6-luna-high",
            "agent_model_id": "gpt-5.6-luna",
        }
    )
    assert payload.agent_profile_id == "codex-gpt-5.6-luna-high"


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


def test_admin_lists_all_supported_ai_task_configs(client: TestClient, db: Session) -> None:
    _admin(client, db)

    response = client.get("/api/v1/admin/ai/task-configs")

    assert response.status_code == 200, response.text
    assert {item["task_type"] for item in response.json()} == {
        "workout_plan_generation",
        "body_photo_analysis",
        "progress_comparison",
        "food_photo_estimation",
        "food_price_search",
    }
    assert all(item["execution_backend"] == "api" for item in response.json())
    assert all(item["agent_name"] is None for item in response.json())
    assert all(item["agent_model_id"] is None for item in response.json())


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
    assert body["credential"] == {"configured": True, "masked": "********cret"}
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


def test_enabled_api_config_still_requires_a_credential(client: TestClient, db: Session) -> None:
    _admin(client, db)
    response = client.put(
        "/api/v1/admin/ai/task-configs/workout_plan_generation",
        headers=ORIGIN,
        json={
            "enabled": True,
            "execution_backend": "api",
            "primary_model_id": "vendor/text-model",
        },
    )
    assert response.status_code == 422
    assert "credential" in response.text.lower()


@pytest.mark.parametrize(
    ("payload", "missing"),
    [
        ({"agent_model_id": "gpt-5-codex"}, "name"),
        ({"agent_name": "codex"}, "model"),
    ],
)
def test_agent_service_config_requires_each_agent_field(
    client: TestClient,
    db: Session,
    payload: dict[str, str],
    missing: str,
) -> None:
    _admin(client, db)
    response = client.put(
        "/api/v1/admin/ai/task-configs/workout_plan_generation",
        headers=ORIGIN,
        json={"enabled": True, "execution_backend": "agent_service", **payload},
    )
    assert response.status_code == 422
    assert missing in response.text.lower()


def test_agent_service_config_exposes_routing(client: TestClient, db: Session) -> None:
    _admin(client, db)
    db.add(
        AIAgentProfileVerification(
            profile_id="codex-gpt-5-codex-high",
            task_type=AITaskType.WORKOUT_PLAN_GENERATION,
            profile_fingerprint="a" * 64,
            status="passed",
            checked_at=datetime.now(UTC),
        )
    )
    db.commit()
    saved = client.put(
        "/api/v1/admin/ai/task-configs/workout_plan_generation",
        headers=ORIGIN,
        json={
            "enabled": True,
            "execution_backend": "agent_service",
            "agent_name": AIAgentName.CODEX,
            "agent_model_id": "gpt-5-codex",
            "agent_profile_id": "codex-gpt-5-codex-high",
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["execution_backend"] == "agent_service"
    assert saved.json()["agent_name"] == "codex"
    assert saved.json()["agent_model_id"] == "gpt-5-codex"
    assert saved.json()["agent_profile_id"] == "codex-gpt-5-codex-high"


def test_agent_service_does_not_require_api_credential_or_catalog(
    client: TestClient, db: Session
) -> None:
    _admin(client, db)
    db.add(
        AIAgentProfileVerification(
            profile_id="antigravity-vision-agent-high",
            task_type=AITaskType.BODY_PHOTO_ANALYSIS,
            profile_fingerprint="b" * 64,
            status="passed",
            checked_at=datetime.now(UTC),
        )
    )
    db.commit()
    response = client.put(
        "/api/v1/admin/ai/task-configs/body_photo_analysis",
        headers=ORIGIN,
        json={
            "enabled": True,
            "execution_backend": "agent_service",
            "agent_name": "antigravity",
            "agent_model_id": "vision-agent",
            "agent_profile_id": "antigravity-vision-agent-high",
        },
    )
    assert response.status_code == 200, response.text


def test_agent_service_rejects_unsupported_task(client: TestClient, db: Session) -> None:
    _admin(client, db)
    response = client.put(
        "/api/v1/admin/ai/task-configs/progress_comparison",
        headers=ORIGIN,
        json={
            "enabled": True,
            "execution_backend": "agent_service",
            "agent_name": "claude",
            "agent_model_id": "claude-sonnet",
        },
    )
    assert response.status_code == 422
    assert "not supported" in response.text.lower()


def test_agent_service_rejects_a_blank_model_id(client: TestClient, db: Session) -> None:
    _admin(client, db)
    response = client.put(
        "/api/v1/admin/ai/task-configs/body_photo_analysis",
        headers=ORIGIN,
        json={
            "enabled": True,
            "execution_backend": "agent_service",
            "agent_name": "antigravity",
            "agent_model_id": "   ",
        },
    )
    assert response.status_code == 422


def test_switching_api_to_agent_and_back_preserves_both_sides(
    client: TestClient, db: Session, test_settings: Settings
) -> None:
    _admin(client, db)
    test_settings.ai_credential_encryption_key = Fernet.generate_key().decode()
    credential = client.put(
        "/api/v1/admin/ai/task-configs/workout_plan_generation",
        headers=ORIGIN,
        json={
            "enabled": False,
            "api_key": "sk-openrouter-secret",
            "replace_credential": True,
        },
    )
    assert credential.status_code == 200, credential.text
    db.add(
        AIModelCatalogEntry(
            provider="openrouter",
            model_id="vendor/text-model",
            display_name="Text Model",
            provider_family="vendor",
            supports_text_input=True,
            supports_image_input=False,
            supports_structured_output=True,
            context_length=32_000,
            input_price_per_token=None,
            output_price_per_token=None,
            refreshed_at=datetime.now(UTC),
        )
    )
    db.commit()
    api_saved = client.put(
        "/api/v1/admin/ai/task-configs/workout_plan_generation",
        headers=ORIGIN,
        json={
            "enabled": True,
            "execution_backend": "api",
            "primary_model_id": "vendor/text-model",
        },
    )
    assert api_saved.status_code == 200, api_saved.text

    db.add(
        AIAgentProfileVerification(
            profile_id="claude-saved-agent-model-high",
            task_type=AITaskType.WORKOUT_PLAN_GENERATION,
            profile_fingerprint="c" * 64,
            status="passed",
            checked_at=datetime.now(UTC),
        )
    )
    db.commit()
    agent_saved = client.put(
        "/api/v1/admin/ai/task-configs/workout_plan_generation",
        headers=ORIGIN,
        json={
            "enabled": True,
            "execution_backend": "agent_service",
            "agent_name": "claude",
            "agent_model_id": "saved-agent-model",
            "agent_profile_id": "claude-saved-agent-model-high",
        },
    )
    assert agent_saved.status_code == 200, agent_saved.text
    assert agent_saved.json()["primary_model_id"] == "vendor/text-model"

    api_restored = client.put(
        "/api/v1/admin/ai/task-configs/workout_plan_generation",
        headers=ORIGIN,
        json={"enabled": True, "execution_backend": "api"},
    )
    assert api_restored.status_code == 200, api_restored.text
    assert api_restored.json()["primary_model_id"] == "vendor/text-model"
    assert api_restored.json()["agent_name"] == "claude"
    assert api_restored.json()["agent_model_id"] == "saved-agent-model"


def test_agent_service_capabilities_require_admin_and_normalize_runner_metadata(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    assert client.get("/api/v1/admin/ai/agent-service/capabilities").status_code == 401
    _register(client, "task-agent-member@example.com")
    assert client.get("/api/v1/admin/ai/agent-service/capabilities").status_code == 403
    _admin(client, db)
    test_settings.agent_service_token = "agent-service-test-token-with-32-bytes-123"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/capabilities"
        assert request.headers["authorization"] == (
            "Bearer agent-service-test-token-with-32-bytes-123"
        )
        return httpx.Response(
            200,
            json={
                "runners": [
                    {
                        "agent": "antigravity",
                        "installed": True,
                        "version": "1.1.22",
                        "auth_state": "authenticated",
                        "auth_mode": "unknown",
                        "models": [
                            {
                                "model_id": "gemini-2.5-pro",
                                "supports_text_input": True,
                                "supports_image_input": True,
                                "supports_structured_output": True,
                            }
                        ],
                    },
                    {
                        "agent": "codex",
                        "installed": False,
                        "version": None,
                        "auth_state": "unauthenticated",
                        "auth_mode": "unknown",
                        "models": [],
                    },
                ]
            },
        )

    replacement = _mock_agent_service(client, httpx.MockTransport(handler))
    try:
        response = client.get("/api/v1/admin/ai/agent-service/capabilities")
    finally:
        _restore_agent_service(client, replacement)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "runners": [
            {
                "agent": "antigravity",
                "installed": True,
                "version": "1.1.22",
                "auth_state": "authenticated",
                "auth_mode": "unknown",
                "models": [
                    {
                        "model_id": "gemini-2.5-pro",
                        "supports_text_input": True,
                        "supports_image_input": True,
                        "supports_structured_output": True,
                    }
                ],
            },
            {
                "agent": "codex",
                "installed": False,
                "version": None,
                "auth_state": "unauthenticated",
                "auth_mode": "unknown",
                "models": [],
            },
        ]
    }


def test_agent_service_capabilities_map_unavailable_to_safe_error(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    _admin(client, db)
    test_settings.agent_service_token = "agent-service-test-token-with-32-bytes-123"
    replacement = _mock_agent_service(
        client,
        httpx.MockTransport(
            lambda _request: httpx.Response(
                503,
                json={
                    "error": {
                        "code": "provider_unavailable",
                        "message": "internal credential secret",
                        "request_id": "internal-request-id",
                    }
                },
            )
        ),
    )
    try:
        response = client.get("/api/v1/admin/ai/agent-service/capabilities")
    finally:
        _restore_agent_service(client, replacement)

    assert response.status_code == 502
    assert "internal credential secret" not in response.text
    assert "agent-service-test-token" not in response.text
    assert "internal-request-id" not in response.text


def test_agent_service_capabilities_fail_closed_without_internal_token(
    client: TestClient,
    db: Session,
) -> None:
    _admin(client, db)

    response = client.get("/api/v1/admin/ai/agent-service/capabilities")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "AGENT_SERVICE_NOT_CONFIGURED"
    assert "token" not in response.text.lower()


def test_agent_service_test_requires_trusted_origin_and_forwards_selection(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    _admin(client, db)
    test_settings.agent_service_token = "agent-service-test-token-with-32-bytes-123"
    seen: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/test"
        assert request.headers["authorization"] == (
            "Bearer agent-service-test-token-with-32-bytes-123"
        )
        seen.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "ok": True,
                "agent": "antigravity",
                "model_id": "gemini-2.5-pro",
                "request_id": "service-request-id",
                "duration_seconds": 0.2,
            },
        )

    replacement = _mock_agent_service(client, httpx.MockTransport(handler))
    try:
        without_origin = client.post(
            "/api/v1/admin/ai/agent-service/test",
            json={"agent": "antigravity", "model_id": "gemini-2.5-pro"},
        )
        response = client.post(
            "/api/v1/admin/ai/agent-service/test",
            headers=ORIGIN,
            json={"agent": "antigravity", "model_id": "gemini-2.5-pro"},
        )
    finally:
        _restore_agent_service(client, replacement)

    assert without_origin.status_code == 403
    assert response.status_code == 200, response.text
    assert response.json()["ok"] is True
    assert response.json()["agent"] == "antigravity"
    assert response.json()["model_id"] == "gemini-2.5-pro"
    assert "service-request-id" not in response.text
    assert "agent-service-test-token" not in response.text
    assert seen == [{"agent": "antigravity", "model_id": "gemini-2.5-pro"}]


def test_agent_service_test_returns_safe_failure_without_internal_details(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    _admin(client, db)
    test_settings.agent_service_token = "agent-service-test-token-with-32-bytes-123"
    replacement = _mock_agent_service(
        client,
        httpx.MockTransport(
            lambda _request: httpx.Response(
                401,
                json={
                    "error": {
                        "code": "unauthorized",
                        "message": "token should never be shown",
                        "request_id": "private-request-id",
                    }
                },
            )
        ),
    )
    try:
        response = client.post(
            "/api/v1/admin/ai/agent-service/test",
            headers=ORIGIN,
            json={"agent": "claude", "model_id": "claude-sonnet"},
        )
    finally:
        _restore_agent_service(client, replacement)

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["error_code"] == "unauthorized"
    assert "token should never be shown" not in response.text
    assert "private-request-id" not in response.text
    assert "agent-service-test-token" not in response.text
