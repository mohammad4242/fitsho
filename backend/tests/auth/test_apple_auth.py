from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import MobileTokenFamily, User


class StubAppleIdentityProvider:
    def __init__(
        self,
        *,
        sub: str = "apple-sub-1",
        email: str | None = "member@privaterelay.appleid.com",
        email_verified: bool = True,
        error: Exception | None = None,
    ) -> None:
        self.identity = SimpleNamespace(
            sub=sub,
            email=email,
            email_verified=email_verified,
            name="Fitician Member",
            picture=None,
        )
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def verify(self, credential: str, nonce: str) -> SimpleNamespace:
        self.calls.append((credential, nonce))
        if self.error is not None:
            raise self.error
        return self.identity


def _apple_login(
    client: TestClient,
    provider: StubAppleIdentityProvider,
    *,
    platform: str = "ios",
):
    client.app.state.apple_identity_provider = provider
    return client.post(
        "/api/v1/auth/mobile/apple",
        json={
            "app_version": "1.0.0",
            "device_id": "iphone-test-1",
            "device_name": "iPhone",
            "identity_token": "signed-apple-id-token",
            "nonce": "nonce-1",
            "platform": platform,
        },
    )


def test_valid_apple_token_creates_user_and_opaque_mobile_session(
    client: TestClient,
    db: Session,
) -> None:
    provider = StubAppleIdentityProvider()

    response = _apple_login(client, provider)

    assert response.status_code == 200
    assert response.json()["token_type"] == "Bearer"
    assert response.json()["user"]["email"] == "member@privaterelay.appleid.com"
    assert provider.calls == [("signed-apple-id-token", "nonce-1")]
    user = db.scalar(select(User).where(User.apple_sub == "apple-sub-1"))
    assert user is not None
    assert (
        db.scalar(select(MobileTokenFamily).where(MobileTokenFamily.user_id == user.id))
        is not None
    )


def test_mobile_apple_auth_is_iOS_only(client: TestClient) -> None:
    provider = StubAppleIdentityProvider()

    response = _apple_login(client, provider, platform="android")

    assert response.status_code == 400
    assert response.json() == {"detail": "Apple authentication is only available on iOS"}
    assert provider.calls == []


def test_same_apple_subject_reuses_user_without_replacing_private_relay_email(
    client: TestClient,
    db: Session,
) -> None:
    first = _apple_login(client, StubAppleIdentityProvider())
    second = _apple_login(
        client,
        StubAppleIdentityProvider(email="new-address@privaterelay.appleid.com"),
    )

    assert first.status_code == second.status_code == 200
    assert first.json()["user"]["id"] == second.json()["user"]["id"]
    assert (
        db.scalar(select(func.count()).select_from(User).where(User.apple_sub == "apple-sub-1"))
        == 1
    )
    user = db.scalar(select(User).where(User.apple_sub == "apple-sub-1"))
    assert user is not None
    assert user.email == "member@privaterelay.appleid.com"


def test_verified_apple_email_links_existing_password_account(
    client: TestClient,
    db: Session,
) -> None:
    registered = client.post(
        "/api/v1/auth/register",
        headers={"Origin": "http://localhost:5173"},
        json={"email": "Member@Example.com", "password": "long password"},
    )

    response = _apple_login(
        client,
        StubAppleIdentityProvider(email="member@example.com"),
    )

    assert registered.status_code == 201
    assert response.status_code == 200
    user = db.get(User, registered.json()["id"])
    assert user is not None
    assert user.apple_sub == "apple-sub-1"
    assert (
        db.scalar(select(func.count()).select_from(User).where(User.email == "member@example.com"))
        == 1
    )


def test_apple_identity_conflict_is_safe(
    client: TestClient,
    db: Session,
) -> None:
    user = User(
        email="member@example.com",
        password_hash="existing-password-hash",
        apple_sub="existing-apple-sub",
    )
    db.add(user)
    db.commit()

    response = _apple_login(client, StubAppleIdentityProvider(email="member@example.com"))

    assert response.status_code == 409
    assert response.json() == {"detail": "Unable to use this Apple account"}
    db.refresh(user)
    assert user.apple_sub == "existing-apple-sub"


@pytest.mark.parametrize("provider_error", [ValueError("invalid signature"), ValueError("expired")])
def test_invalid_apple_tokens_use_one_safe_error(
    client: TestClient,
    provider_error: ValueError,
) -> None:
    response = _apple_login(client, StubAppleIdentityProvider(error=provider_error))

    assert response.status_code == 401
    assert response.json() == {"detail": "Apple authentication failed"}
    assert "signed-apple-id-token" not in response.text


def test_database_identity_constraint_allows_apple_only_user(db: Session) -> None:
    user = User(apple_sub="apple-only-sub")
    db.add(user)
    db.flush()

    assert user.id is not None


def test_database_identity_constraint_rejects_user_without_identity(db: Session) -> None:
    db.add(User())

    with pytest.raises(IntegrityError):
        db.flush()
