import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.config import Settings
from app.main import create_app

TOKEN = "a" * 32


def client() -> TestClient:
    return TestClient(create_app(Settings(agent_service_token=SecretStr(TOKEN))))


def test_capabilities_requires_bearer_token() -> None:
    response = client().get("/v1/capabilities")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "unauthorized"
    assert "request_id" in response.json()["error"]


@pytest.mark.parametrize("header", ["Basic abc", "Bearer", "Bearer ", "Bearer wrong"])
def test_capabilities_rejects_malformed_or_wrong_token(header: str) -> None:
    response = client().get("/v1/capabilities", headers={"Authorization": header})
    assert response.status_code == 401
    assert TOKEN not in response.text


def test_capabilities_accepts_correct_token_and_is_empty() -> None:
    response = client().get("/v1/capabilities", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    assert response.json() == {"runners": []}


def test_config_rejects_short_token() -> None:
    with pytest.raises(ValidationError):
        Settings(agent_service_token=SecretStr("too-short"))


def test_error_does_not_echo_token() -> None:
    response = client().get("/v1/capabilities", headers={"Authorization": f"Bearer {'b' * 32}"})
    assert "b" * 32 not in response.text
