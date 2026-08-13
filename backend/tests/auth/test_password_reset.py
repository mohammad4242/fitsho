from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import AuthSession, PasswordResetToken, User
from app.auth.security import hash_password_reset_token, verify_password

ORIGIN = {"Origin": "http://localhost:5173"}
GENERIC_RESPONSE = {"message": "If the account exists, a reset link has been sent."}


def _register(client: TestClient, email: str = "reset@example.com") -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "old password"},
    )
    assert response.status_code == 201


def _raw_token(client: TestClient) -> str:
    provider = client.app.state.email_provider
    reset_url = provider.deliveries[-1].reset_url
    return parse_qs(urlsplit(reset_url).query)["token"][0]


def test_forgot_password_has_the_same_response_for_known_and_unknown_email(
    client: TestClient,
) -> None:
    _register(client)
    client.app.state.email_provider.deliveries.clear()

    known = client.post(
        "/api/v1/auth/forgot-password",
        headers=ORIGIN,
        json={"email": "RESET@example.com"},
    )
    unknown = client.post(
        "/api/v1/auth/forgot-password",
        headers=ORIGIN,
        json={"email": "unknown@example.com"},
    )

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json() == GENERIC_RESPONSE
    assert len(client.app.state.email_provider.deliveries) == 1


def test_forgot_password_stores_only_the_reset_token_hash(
    client: TestClient,
    db: Session,
) -> None:
    _register(client)
    client.post(
        "/api/v1/auth/forgot-password",
        headers=ORIGIN,
        json={"email": "reset@example.com"},
    )
    raw_token = _raw_token(client)
    stored = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_password_reset_token(raw_token)
        )
    )

    assert stored is not None
    assert raw_token not in stored.token_hash


def test_reset_password_is_single_use_and_invalidates_all_sessions(
    client: TestClient,
    db: Session,
) -> None:
    _register(client)
    user = db.scalar(select(User).where(User.email == "reset@example.com"))
    assert user is not None
    client.post(
        "/api/v1/auth/forgot-password",
        headers=ORIGIN,
        json={"email": "reset@example.com"},
    )
    raw_token = _raw_token(client)

    reset = client.post(
        "/api/v1/auth/reset-password",
        headers=ORIGIN,
        json={"token": raw_token, "password": "new secure password"},
    )
    reused = client.post(
        "/api/v1/auth/reset-password",
        headers=ORIGIN,
        json={"token": raw_token, "password": "another password"},
    )

    db.refresh(user)
    assert reset.status_code == 204
    assert reused.status_code == 400
    assert reused.json() == {"detail": "Invalid or expired reset token"}
    assert user.password_hash is not None
    assert verify_password("new secure password", user.password_hash)
    assert db.scalars(select(AuthSession).where(AuthSession.user_id == user.id)).all() == []
    assert client.get("/api/v1/auth/me").status_code == 401

    login = client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": "reset@example.com", "password": "new secure password"},
    )
    assert login.status_code == 200


def test_expired_or_unknown_reset_token_uses_the_same_error(
    client: TestClient,
    db: Session,
) -> None:
    _register(client)
    client.post(
        "/api/v1/auth/forgot-password",
        headers=ORIGIN,
        json={"email": "reset@example.com"},
    )
    raw_token = _raw_token(client)
    stored = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_password_reset_token(raw_token)
        )
    )
    assert stored is not None
    stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    expired = client.post(
        "/api/v1/auth/reset-password",
        headers=ORIGIN,
        json={"token": raw_token, "password": "new secure password"},
    )
    unknown = client.post(
        "/api/v1/auth/reset-password",
        headers=ORIGIN,
        json={"token": "unknown-token", "password": "new secure password"},
    )

    assert expired.status_code == unknown.status_code == 400
    assert expired.json() == unknown.json() == {"detail": "Invalid or expired reset token"}


def test_password_recovery_requires_a_trusted_origin(client: TestClient) -> None:
    forgot = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "reset@example.com"},
    )
    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "unknown-token", "password": "new secure password"},
    )

    assert forgot.status_code == reset.status_code == 403
