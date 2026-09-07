from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import models, security
from app.auth.models import User

ORIGIN = {"Origin": "http://localhost:5173"}
GENERIC_RESPONSE = {"message": "If verification is available, an email has been sent."}


def _register(client: TestClient, email: str = "verify@example.com") -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201
    return response.json()


def _raw_verification_token(client: TestClient) -> str:
    assert hasattr(client.app.state.email_provider, "verification_deliveries")
    delivery = client.app.state.email_provider.verification_deliveries[-1]
    return parse_qs(urlsplit(delivery.verification_url).query)["token"][0]


def test_registration_sends_verification_and_stores_only_token_hash(
    client: TestClient,
    db: Session,
) -> None:
    registered = _register(client)
    raw_token = _raw_verification_token(client)
    assert hasattr(models, "EmailVerificationToken")
    assert hasattr(security, "hash_email_verification_token")
    stored = db.scalar(
        select(models.EmailVerificationToken).where(
            models.EmailVerificationToken.token_hash
            == security.hash_email_verification_token(raw_token)
        )
    )

    assert stored is not None
    assert str(stored.user_id) == registered["id"]
    assert raw_token not in stored.token_hash


def test_verification_marks_email_verified_and_token_is_single_use(
    client: TestClient,
    db: Session,
) -> None:
    registered = _register(client)
    raw_token = _raw_verification_token(client)

    verified = client.post(
        "/api/v1/auth/email/verify",
        headers=ORIGIN,
        json={"token": raw_token},
    )
    reused = client.post(
        "/api/v1/auth/email/verify",
        headers=ORIGIN,
        json={"token": raw_token},
    )

    assert verified.status_code == 204
    assert reused.status_code == 400
    user = db.get(User, registered["id"])
    assert user is not None
    assert user.email_verified_at is not None
    assert client.app.state.email_provider.welcome_deliveries[-1].recipient == user.email


def test_expired_email_verification_token_fails(client: TestClient, db: Session) -> None:
    _register(client)
    raw_token = _raw_verification_token(client)
    assert hasattr(models, "EmailVerificationToken")
    assert hasattr(security, "hash_email_verification_token")
    stored = db.scalar(
        select(models.EmailVerificationToken).where(
            models.EmailVerificationToken.token_hash
            == security.hash_email_verification_token(raw_token)
        )
    )
    assert stored is not None
    stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    response = client.post(
        "/api/v1/auth/email/verify",
        headers=ORIGIN,
        json={"token": raw_token},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid or expired verification token"}


def test_authenticated_user_can_request_another_verification(client: TestClient) -> None:
    _register(client)
    client.app.state.email_provider.verification_deliveries.clear()

    response = client.post("/api/v1/auth/email/send-verification", headers=ORIGIN)

    assert response.status_code == 202
    assert response.json() == GENERIC_RESPONSE
    assert len(client.app.state.email_provider.verification_deliveries) == 1


def test_verification_endpoints_require_expected_auth_and_origin(client: TestClient) -> None:
    send = client.post("/api/v1/auth/email/send-verification", headers=ORIGIN)
    verify = client.post(
        "/api/v1/auth/email/verify",
        json={"token": "unknown-token"},
    )

    assert send.status_code == 401
    assert verify.status_code == 403
