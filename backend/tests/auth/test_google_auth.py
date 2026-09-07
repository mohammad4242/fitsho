from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.models import AuthSession, User

ORIGIN = {"Origin": "http://localhost:5173"}


class StubGoogleIdentityProvider:
    def __init__(
        self,
        *,
        sub: str = "google-sub-1",
        email: str | None = "member@example.com",
        email_verified: bool = True,
        error: Exception | None = None,
    ) -> None:
        self.identity = SimpleNamespace(
            sub=sub,
            email=email,
            email_verified=email_verified,
            name="Fitsho Member",
            picture="https://example.com/avatar.jpg",
        )
        self.error = error
        self.credentials: list[str] = []

    def verify(self, credential: str) -> SimpleNamespace:
        self.credentials.append(credential)
        if self.error is not None:
            raise self.error
        return self.identity


def _google_login(client: TestClient, provider: StubGoogleIdentityProvider):
    client.app.state.google_identity_provider = provider
    return client.post(
        "/api/v1/auth/google",
        headers=ORIGIN,
        json={"credential": "signed-google-id-token"},
    )


def test_valid_google_token_creates_user_auth_session_and_cookie(
    client: TestClient,
    db: Session,
) -> None:
    response = _google_login(client, StubGoogleIdentityProvider())

    assert response.status_code == 200
    assert response.json()["email"] == "member@example.com"
    assert "fitsho_session" in response.cookies
    user = db.scalar(select(User).where(User.google_sub == "google-sub-1"))
    assert user is not None
    assert user.password_hash is None
    assert user.email_verified_at is not None
    assert db.scalar(select(AuthSession).where(AuthSession.user_id == user.id)) is not None


def test_same_google_sub_reuses_the_same_user(client: TestClient, db: Session) -> None:
    first = _google_login(client, StubGoogleIdentityProvider())
    second = _google_login(client, StubGoogleIdentityProvider(email="new-address@example.com"))

    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert db.scalar(select(func.count()).select_from(User)) == 1


def test_verified_google_email_links_existing_password_account(
    client: TestClient,
    db: Session,
) -> None:
    registered = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": "Member@Example.com", "password": "long password"},
    )
    client.post("/api/v1/auth/logout", headers=ORIGIN)

    google = _google_login(
        client,
        StubGoogleIdentityProvider(email="member@example.com", email_verified=True),
    )

    assert google.status_code == 200
    assert google.json()["id"] == registered.json()["id"]
    user = db.get(User, registered.json()["id"])
    assert user is not None
    assert user.google_sub == "google-sub-1"
    assert user.email_verified_at is not None
    assert db.scalar(select(func.count()).select_from(User)) == 1


def test_google_does_not_overwrite_a_conflicting_identity(
    client: TestClient,
    db: Session,
) -> None:
    user = User(
        email="member@example.com",
        password_hash="existing-password-hash",
        google_sub="existing-google-sub",
    )
    db.add(user)
    db.commit()

    response = _google_login(
        client,
        StubGoogleIdentityProvider(sub="different-google-sub"),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Unable to use this Google account"}
    db.refresh(user)
    assert user.google_sub == "existing-google-sub"
    assert db.scalar(select(func.count()).select_from(User)) == 1


def test_unverified_google_email_is_not_linked_to_existing_account(
    client: TestClient,
    db: Session,
) -> None:
    registered = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": "member@example.com", "password": "long password"},
    )

    response = _google_login(
        client,
        StubGoogleIdentityProvider(email_verified=False),
    )

    assert response.status_code == 409
    user = db.get(User, registered.json()["id"])
    assert user is not None
    assert user.google_sub is None
    assert db.scalar(select(func.count()).select_from(User)) == 1


def test_unverified_google_identity_without_conflict_creates_google_only_user(
    client: TestClient,
    db: Session,
) -> None:
    response = _google_login(
        client,
        StubGoogleIdentityProvider(email="untrusted@example.com", email_verified=False),
    )

    assert response.status_code == 200
    user = db.scalar(select(User).where(User.google_sub == "google-sub-1"))
    assert user is not None
    assert user.email is None
    assert user.password_hash is None
    assert user.email_verified_at is None


def test_verified_email_completes_an_existing_google_only_user(
    client: TestClient,
    db: Session,
) -> None:
    first = _google_login(
        client,
        StubGoogleIdentityProvider(email=None, email_verified=False),
    )
    second = _google_login(
        client,
        StubGoogleIdentityProvider(email="verified@example.com", email_verified=True),
    )

    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    user = db.scalar(select(User).where(User.google_sub == "google-sub-1"))
    assert user is not None
    assert user.email == "verified@example.com"
    assert user.email_verified_at is not None
    assert db.scalar(select(func.count()).select_from(User)) == 1


@pytest.mark.parametrize(
    "provider_error",
    [
        ValueError("invalid signature"),
        ValueError("wrong audience"),
        ValueError("expired token"),
    ],
)
def test_invalid_google_tokens_use_one_safe_error(
    client: TestClient,
    provider_error: ValueError,
) -> None:
    response = _google_login(
        client,
        StubGoogleIdentityProvider(error=provider_error),
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Google authentication failed"}
    assert "signed-google-id-token" not in response.text


def test_google_auth_requires_trusted_origin(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/google",
        json={"credential": "signed-google-id-token"},
    )

    assert response.status_code == 403


def test_database_identity_constraint_allows_google_only_user(db: Session) -> None:
    user = User(google_sub="google-only-sub")
    db.add(user)
    db.flush()

    assert user.id is not None


def test_database_identity_constraint_rejects_user_without_identity(db: Session) -> None:
    db.add(User())

    with pytest.raises(IntegrityError):
        db.flush()
