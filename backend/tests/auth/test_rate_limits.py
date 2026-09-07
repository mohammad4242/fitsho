from fastapi.testclient import TestClient

from app.config import Settings

ORIGIN = {"Origin": "http://localhost:5173"}


def test_forgot_password_rate_limit_is_generic(
    client: TestClient,
    test_settings: Settings,
) -> None:
    test_settings.auth_forgot_password_ip_limit = 1
    payload = {"email": "unknown@example.com"}

    first = client.post("/api/v1/auth/forgot-password", headers=ORIGIN, json=payload)
    limited = client.post("/api/v1/auth/forgot-password", headers=ORIGIN, json=payload)

    assert first.status_code == 202
    assert limited.status_code == 429
    assert limited.json() == {"detail": "Too many authentication requests"}


def test_phone_send_rate_limit_does_not_reveal_account_state(
    client: TestClient,
    test_settings: Settings,
) -> None:
    test_settings.auth_phone_otp_ip_limit = 1

    first = client.post(
        "/api/v1/auth/phone/send-otp",
        headers=ORIGIN,
        json={"phone_number": "09123456789"},
    )
    limited = client.post(
        "/api/v1/auth/phone/send-otp",
        headers=ORIGIN,
        json={"phone_number": "09351234567"},
    )

    assert first.status_code == 202
    assert limited.status_code == 429
    assert limited.json() == {"detail": "Too many authentication requests"}
