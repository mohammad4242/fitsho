from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.main import create_app


def test_health_is_unauthenticated_and_exact() -> None:
    app = create_app(Settings(agent_service_token=SecretStr("a" * 32)))
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_unknown_route_uses_the_safe_error_envelope() -> None:
    app = create_app(Settings(agent_service_token=SecretStr("a" * 32)))
    response = TestClient(app).get("/missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "invalid_request"
    assert "request_id" in response.json()["error"]
