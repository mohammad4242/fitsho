from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.auth.models import AuthSession, User
from app.config import Settings
from app.database.session import get_db
from app.main import create_app


def test_register_creates_user_session_and_cookie(client: TestClient, db: Session) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers={"Origin": "http://localhost:5173"},
        json={"email": " New@Example.com ", "password": "long password"},
    )

    assert response.status_code == 201
    assert response.json()["email"] == "new@example.com"
    assert "password_hash" not in response.json()
    assert "fitsho_session" in response.cookies
    user = db.scalar(select(User).where(User.email == "new@example.com"))
    assert user is not None
    assert user.password_hash != "long password"
    assert db.scalar(select(AuthSession).where(AuthSession.user_id == user.id)) is not None


def test_register_rejects_duplicate_email(client: TestClient) -> None:
    payload = {"email": "duplicate@example.com", "password": "long password"}
    headers = {"Origin": "http://localhost:5173"}

    assert client.post("/api/v1/auth/register", headers=headers, json=payload).status_code == 201
    response = client.post("/api/v1/auth/register", headers=headers, json=payload)

    assert response.status_code == 409
    assert response.json() == {"detail": "Email is already registered"}


def test_register_rejects_invalid_input(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers={"Origin": "http://localhost:5173"},
        json={"email": "invalid", "password": "short"},
    )

    assert response.status_code == 422


def test_register_rejects_untrusted_or_missing_origin(client: TestClient) -> None:
    payload = {"email": "origin@example.com", "password": "long password"}

    assert client.post("/api/v1/auth/register", json=payload).status_code == 403
    assert (
        client.post(
            "/api/v1/auth/register",
            headers={"Origin": "https://evil.example"},
            json=payload,
        ).status_code
        == 403
    )


def test_database_failure_returns_503_and_rolls_back_user(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_commit = db.commit

    def unavailable_commit() -> None:
        raise OperationalError("COMMIT", {}, Exception("database unavailable"))

    monkeypatch.setattr(db, "commit", unavailable_commit)
    response = client.post(
        "/api/v1/auth/register",
        headers={"Origin": "http://localhost:5173"},
        json={"email": "rollback@example.com", "password": "long password"},
    )
    monkeypatch.setattr(db, "commit", original_commit)

    assert response.status_code == 503
    assert response.json() == {"detail": "Service temporarily unavailable"}
    assert db.scalar(select(User).where(User.email == "rollback@example.com")) is None


def test_production_cookie_uses_host_security_prefix(
    db: Session,
    test_settings: Settings,
) -> None:
    production_settings = test_settings.model_copy(
        update={
            "app_env": "production",
            "frontend_origin": "https://fitsho.example",
            "cookie_secure": True,
            "session_cookie_name": "__Host-fitsho_session",
        }
    )
    app = create_app(production_settings)

    def override_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app, base_url="https://testserver") as secure_client:
        response = secure_client.post(
            "/api/v1/auth/register",
            headers={"Origin": "https://fitsho.example"},
            json={"email": "secure@example.com", "password": "long password"},
        )

    cookie = response.headers["set-cookie"]
    assert response.status_code == 201
    assert cookie.startswith("__Host-fitsho_session=")
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert "Domain=" not in cookie
