from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.notifications.models import (
    NotificationDevice,
    NotificationDeviceToken,
    NotificationPreference,
)

ORIGIN = {"Origin": "http://localhost:5173"}


def _register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201
    client.post("/api/v1/auth/logout", headers=ORIGIN)


def _login(
    client: TestClient,
    email: str,
    device_id: str = "android-device-1",
    platform: str = "android",
) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/mobile/password",
        json={
            "email": email,
            "password": "long password",
            "device_id": device_id,
            "platform": platform,
            "app_version": "1.0.0",
            "device_name": "Pixel",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_current_mobile_device_registers_and_rotates_a_single_active_token(
    client: TestClient,
    db: Session,
) -> None:
    _register(client, "member@example.com")
    auth = _login(client, "member@example.com")

    first = client.put(
        "/api/v1/notifications/devices/current",
        headers={"Authorization": f"Bearer {auth['access_token']}"},
        json={"provider": "fcm", "token": "fcm-token-1"},
    )

    assert first.status_code == 200
    first_body = first.json()
    assert first_body["device_id"] == "android-device-1"
    assert first_body["platform"] == "android"
    assert first_body["has_active_token"] is True
    assert "token" not in first_body
    device_uuid = first_body["id"]

    second = client.put(
        "/api/v1/notifications/devices/current",
        headers={"Authorization": f"Bearer {auth['access_token']}"},
        json={"provider": "fcm", "token": "fcm-token-2"},
    )

    assert second.status_code == 200
    assert second.json()["id"] == device_uuid
    device = db.get(NotificationDevice, device_uuid)
    assert device is not None
    tokens = db.scalars(
        select(NotificationDeviceToken).where(NotificationDeviceToken.device_id == device.id)
    ).all()
    assert len(tokens) == 2
    assert sum(token.invalid_at is None for token in tokens) == 1
    assert {token.token_value for token in tokens} == {"fcm-token-1", "fcm-token-2"}

    listed = client.get(
        "/api/v1/notifications/devices",
        headers={"Authorization": f"Bearer {auth['access_token']}"},
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["has_active_token"] is True
    assert all("token" not in item for item in listed.json())


def test_notification_endpoints_require_native_bearer_auth(client: TestClient) -> None:
    _register(client, "cookie-member@example.com")
    client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": "cookie-member-2@example.com", "password": "long password"},
    )

    response = client.get("/api/v1/notifications/preferences")

    assert response.status_code == 401
    assert response.json()["detail"] == "Bearer authentication required"


def test_notification_devices_are_user_scoped_and_delete_cascades_tokens(
    client: TestClient,
    db: Session,
) -> None:
    _register(client, "first@example.com")
    first_auth = _login(client, "first@example.com")
    first = client.put(
        "/api/v1/notifications/devices/current",
        headers={"Authorization": f"Bearer {first_auth['access_token']}"},
        json={"token": "first-token"},
    )
    assert first.status_code == 200
    device_uuid = first.json()["id"]

    _register(client, "second@example.com")
    second_auth = _login(client, "second@example.com", device_id="android-device-2")
    forbidden_delete = client.delete(
        f"/api/v1/notifications/devices/{device_uuid}",
        headers={"Authorization": f"Bearer {second_auth['access_token']}"},
    )

    assert forbidden_delete.status_code == 404
    assert db.get(NotificationDevice, device_uuid) is not None

    deleted = client.delete(
        f"/api/v1/notifications/devices/{device_uuid}",
        headers={"Authorization": f"Bearer {first_auth['access_token']}"},
    )
    assert deleted.status_code == 204
    assert db.get(NotificationDevice, device_uuid) is None
    assert db.scalar(
        select(NotificationDeviceToken).where(NotificationDeviceToken.device_id == device_uuid)
    ) is None


def test_notification_preferences_are_user_scoped_and_default_to_enabled(
    client: TestClient,
    db: Session,
) -> None:
    _register(client, "preferences@example.com")
    auth = _login(client, "preferences@example.com")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}

    default = client.get("/api/v1/notifications/preferences", headers=headers)

    assert default.status_code == 200
    assert default.json()["enabled"] is True
    assert default.json()["approved_plans"] is True
    assert default.json()["required_reviews"] is True
    assert default.json()["body_analysis"] is True
    assert default.json()["cycle_reminders"] is True
    assert default.json()["physician_decisions"] is True
    assert default.json()["nutrition_updates"] is True
    assert default.json()["updated_at"] is None

    updated = client.put(
        "/api/v1/notifications/preferences",
        headers=headers,
        json={
            "enabled": True,
            "approved_plans": False,
            "required_reviews": True,
            "body_analysis": False,
            "cycle_reminders": True,
            "physician_decisions": False,
            "nutrition_updates": False,
        },
    )

    assert updated.status_code == 200
    assert updated.json()["approved_plans"] is False
    assert updated.json()["body_analysis"] is False
    assert updated.json()["physician_decisions"] is False
    assert updated.json()["nutrition_updates"] is False
    assert updated.json()["updated_at"] is not None

    reread = client.get("/api/v1/notifications/preferences", headers=headers)
    assert reread.json() == updated.json()

    from app.auth.models import User

    user = db.scalar(select(User).where(User.email == "preferences@example.com"))
    assert user is not None
    assert db.get(NotificationPreference, user.id) is not None


def test_notification_registration_rejects_unknown_provider(client: TestClient) -> None:
    _register(client, "invalid@example.com")
    auth = _login(client, "invalid@example.com")

    response = client.put(
        "/api/v1/notifications/devices/current",
        headers={"Authorization": f"Bearer {auth['access_token']}"},
        json={"provider": "apns", "token": "token"},
    )

    assert response.status_code == 422


def test_ios_notification_registration_requires_and_stores_an_apns_token(
    client: TestClient,
) -> None:
    _register(client, "ios-member@example.com")
    auth = _login(client, "ios-member@example.com", platform="ios")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}

    apns = client.put(
        "/api/v1/notifications/devices/current",
        headers=headers,
        json={"provider": "apns", "token": "apns-device-token"},
    )
    assert apns.status_code == 200
    assert apns.json()["platform"] == "ios"

    mismatched = client.put(
        "/api/v1/notifications/devices/current",
        headers=headers,
        json={"provider": "fcm", "token": "fcm-token"},
    )
    assert mismatched.status_code == 422
