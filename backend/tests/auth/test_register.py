from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import AuthSession, User


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
