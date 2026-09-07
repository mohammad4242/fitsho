from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import (
    AuthSession,
    MobileAccessToken,
    MobileAuthEvent,
    MobileRefreshToken,
    MobileTokenFamily,
    User,
)
from app.auth.security import hash_mobile_token

ORIGIN = {"Origin": "http://localhost:5173"}
DEVICE = {
    "device_id": "android-device-1",
    "platform": "android",
    "app_version": "1.0.0",
    "device_name": "Pixel",
}


def _register(client: TestClient, email: str = "member@example.com") -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201
    client.post("/api/v1/auth/logout", headers=ORIGIN)


def _password_login(
    client: TestClient,
    *,
    device_id: str = DEVICE["device_id"],
) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/mobile/password",
        json={
            "email": "member@example.com",
            "password": "long password",
            **{**DEVICE, "device_id": device_id},
        },
    )
    assert response.status_code == 200
    return response.json()


def test_mobile_password_login_issues_opaque_tokens_and_bearer_auth(
    client: TestClient,
    db: Session,
) -> None:
    _register(client)

    body = _password_login(client)

    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 900
    assert body["refresh_expires_in"] == 30 * 24 * 60 * 60
    assert body["user"]["email"] == "member@example.com"
    assert "fitsho_session" not in client.cookies
    user = db.scalar(select(User).where(User.email == "member@example.com"))
    assert user is not None
    assert db.scalar(select(AuthSession).where(AuthSession.user_id == user.id)) is None
    access = db.scalar(
        select(MobileAccessToken).where(
            MobileAccessToken.token_hash == hash_mobile_token(body["access_token"])
        )
    )
    refresh = db.scalar(
        select(MobileRefreshToken).where(
            MobileRefreshToken.token_hash == hash_mobile_token(body["refresh_token"])
        )
    )
    assert access is not None
    assert refresh is not None
    assert body["access_token"] not in access.token_hash
    assert body["refresh_token"] not in refresh.token_hash

    current = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert current.status_code == 200
    assert current.json()["id"] == body["user"]["id"]


def test_invalid_bearer_does_not_fall_back_to_a_valid_cookie(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": "cookie-member@example.com", "password": "long password"},
    )
    assert response.status_code == 201

    current = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer forged-mobile-token"},
    )

    assert current.status_code == 401
    assert "Max-Age=0" not in current.headers.get("set-cookie", "")


def test_mobile_refresh_rotates_the_refresh_token(client: TestClient, db: Session) -> None:
    _register(client)
    first = _password_login(client)

    response = client.post(
        "/api/v1/auth/mobile/refresh",
        json={"refresh_token": first["refresh_token"]},
    )

    assert response.status_code == 200
    second = response.json()
    assert second["access_token"] != first["access_token"]
    assert second["refresh_token"] != first["refresh_token"]
    old = db.scalar(
        select(MobileRefreshToken).where(
            MobileRefreshToken.token_hash == hash_mobile_token(first["refresh_token"])
        )
    )
    assert old is not None
    assert old.used_at is not None
    assert old.replaced_by_id is not None


def test_mobile_refresh_replay_revokes_the_family_and_records_an_audit_event(
    client: TestClient,
    db: Session,
) -> None:
    _register(client)
    first = _password_login(client)
    rotated = client.post(
        "/api/v1/auth/mobile/refresh",
        json={"refresh_token": first["refresh_token"]},
    )
    assert rotated.status_code == 200

    replay = client.post(
        "/api/v1/auth/mobile/refresh",
        json={"refresh_token": first["refresh_token"]},
    )

    assert replay.status_code == 401
    assert (
        client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {rotated.json()['access_token']}"},
        ).status_code
        == 401
    )
    old = db.scalar(
        select(MobileRefreshToken).where(
            MobileRefreshToken.token_hash == hash_mobile_token(first["refresh_token"])
        )
    )
    assert old is not None
    family = db.get(MobileTokenFamily, old.family_id)
    assert family is not None
    assert family.revoked_at is not None
    assert db.scalar(
        select(MobileAuthEvent).where(
            MobileAuthEvent.family_id == family.id,
            MobileAuthEvent.event_type == "refresh_replay_detected",
        )
    ) is not None


def test_mobile_refresh_updates_device_last_seen(client: TestClient, db: Session) -> None:
    _register(client)
    first = _password_login(client)
    family = db.scalar(
        select(MobileTokenFamily).where(MobileTokenFamily.device_id == DEVICE["device_id"])
    )
    assert family is not None
    previous_seen = family.last_seen_at

    rotated = client.post(
        "/api/v1/auth/mobile/refresh",
        json={"refresh_token": first["refresh_token"]},
    )

    assert rotated.status_code == 200
    db.refresh(family)
    assert family.last_seen_at >= previous_seen


def test_mobile_logout_revokes_the_current_token_family(client: TestClient, db: Session) -> None:
    _register(client)
    body = _password_login(client)

    response = client.post(
        "/api/v1/auth/mobile/logout",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )

    assert response.status_code == 204
    family = db.scalar(
        select(MobileTokenFamily).where(
            MobileTokenFamily.id
            == db.scalar(
                select(MobileAccessToken.family_id).where(
                    MobileAccessToken.token_hash == hash_mobile_token(body["access_token"])
                )
            )
        )
    )
    assert family is not None
    assert family.revoked_at is not None
    assert (
        client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {body['access_token']}"},
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/mobile/refresh",
            json={"refresh_token": body["refresh_token"]},
        ).status_code
        == 401
    )


def test_mobile_password_login_is_rate_limited_by_ip(
    client: TestClient,
    test_settings,
) -> None:
    test_settings.auth_mobile_password_ip_limit = 1
    payload = {
        "email": "member@example.com",
        "password": "long password",
        **DEVICE,
    }

    first = client.post("/api/v1/auth/mobile/password", json=payload)
    second = client.post("/api/v1/auth/mobile/password", json=payload)

    assert first.status_code == 401
    assert second.status_code == 429


def test_mobile_logout_all_revokes_other_devices(client: TestClient) -> None:
    _register(client)
    first = _password_login(client, device_id="android-device-1")
    second = _password_login(client, device_id="android-device-2")

    response = client.post(
        "/api/v1/auth/mobile/logout-all",
        headers={"Authorization": f"Bearer {first['access_token']}"},
    )

    assert response.status_code == 204
    for token in (first["access_token"], second["access_token"]):
        assert (
            client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            ).status_code
            == 401
        )


def test_mobile_google_login_uses_the_existing_identity_provider(
    client: TestClient,
) -> None:
    client.app.state.google_identity_provider = SimpleNamespace(
        verify=lambda credential: SimpleNamespace(
            sub="google-mobile-sub",
            email="google-mobile@example.com",
            email_verified=True,
        )
    )

    response = client.post(
        "/api/v1/auth/mobile/google",
        json={"credential": "signed-google-id-token", **DEVICE},
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "google-mobile@example.com"
    assert "access_token" in response.json()


def test_mobile_phone_login_uses_verified_otp(client: TestClient) -> None:
    send = client.post(
        "/api/v1/auth/mobile/phone/send-otp",
        json={"phone_number": "09123456789"},
    )
    assert send.status_code == 202
    code = client.app.state.sms_provider.deliveries[-1].code

    response = client.post(
        "/api/v1/auth/mobile/phone/verify-otp",
        json={"phone_number": "09123456789", "code": code, **DEVICE},
    )

    assert response.status_code == 200
    assert response.json()["user"]["phone_number"] == "+989123456789"
    assert "access_token" in response.json()
