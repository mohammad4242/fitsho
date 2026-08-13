from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import PhoneOtpChallenge, User
from app.auth.security import hash_otp_code
from app.config import Settings

ORIGIN = {"Origin": "http://localhost:5173"}
PHONE = "09123456789"
NORMALIZED_PHONE = "+989123456789"
GENERIC_SEND_MESSAGE = "If the number can receive messages, an OTP has been sent."
GENERIC_OTP_ERROR = {"detail": "Invalid or expired OTP"}


def _send(client: TestClient, phone_number: str = PHONE):
    return client.post(
        "/api/v1/auth/phone/send-otp",
        headers=ORIGIN,
        json={"phone_number": phone_number},
    )


def _latest_code(client: TestClient) -> str:
    return client.app.state.sms_provider.deliveries[-1].code


def _verify(client: TestClient, code: str, phone_number: str = PHONE):
    return client.post(
        "/api/v1/auth/phone/verify-otp",
        headers=ORIGIN,
        json={"phone_number": phone_number, "code": code},
    )


def test_send_otp_normalizes_phone_and_stores_only_hmac_hash(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    response = _send(client, "00989123456789")
    code = _latest_code(client)
    challenge = db.scalar(
        select(PhoneOtpChallenge).where(PhoneOtpChallenge.phone_number == NORMALIZED_PHONE)
    )

    assert response.status_code == 202
    assert response.json() == {
        "message": GENERIC_SEND_MESSAGE,
        "retry_after_seconds": 60,
    }
    assert challenge is not None
    assert challenge.code_hash == hash_otp_code(
        NORMALIZED_PHONE,
        code,
        test_settings.phone_otp_hmac_secret.get_secret_value(),
    )
    assert code not in challenge.code_hash


def test_send_otp_enforces_cooldown_then_invalidates_the_previous_code(
    client: TestClient,
    db: Session,
) -> None:
    first = _send(client)
    first_code = _latest_code(client)
    first_challenge = db.scalar(
        select(PhoneOtpChallenge).where(PhoneOtpChallenge.phone_number == NORMALIZED_PHONE)
    )
    assert first_challenge is not None

    cooldown = _send(client)
    assert cooldown.status_code == first.status_code == 202
    assert len(client.app.state.sms_provider.deliveries) == 1

    first_challenge.resend_available_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    resent = _send(client)
    second_code = _latest_code(client)
    db.refresh(first_challenge)

    assert resent.status_code == 202
    assert len(client.app.state.sms_provider.deliveries) == 2
    assert first_challenge.consumed_at is not None
    assert _verify(client, first_code).status_code == 401
    assert _verify(client, second_code).status_code == 200


def test_wrong_otp_consumes_attempts_and_locks_the_challenge(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    _send(client)
    correct_code = _latest_code(client)

    for _ in range(test_settings.phone_otp_max_attempts):
        wrong = _verify(client, "000000" if correct_code != "000000" else "111111")
        assert wrong.status_code == 401
        assert wrong.json() == GENERIC_OTP_ERROR

    challenge = db.scalar(
        select(PhoneOtpChallenge).where(PhoneOtpChallenge.phone_number == NORMALIZED_PHONE)
    )
    assert challenge is not None
    assert challenge.attempts_remaining == 0
    assert _verify(client, correct_code).status_code == 401


def test_expired_unknown_and_reused_otp_have_the_same_error(
    client: TestClient,
    db: Session,
) -> None:
    _send(client)
    code = _latest_code(client)
    challenge = db.scalar(
        select(PhoneOtpChallenge).where(PhoneOtpChallenge.phone_number == NORMALIZED_PHONE)
    )
    assert challenge is not None
    challenge.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    expired = _verify(client, code)
    unknown = _verify(client, "123456", "+989999999999")

    challenge.resend_available_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    _send(client)
    fresh_code = _latest_code(client)
    assert _verify(client, fresh_code).status_code == 200
    reused = _verify(client, fresh_code)

    assert expired.status_code == unknown.status_code == reused.status_code == 401
    assert expired.json() == unknown.json() == reused.json() == GENERIC_OTP_ERROR


def test_successful_otp_creates_phone_user_and_existing_session_cookie(
    client: TestClient,
    db: Session,
) -> None:
    _send(client)
    response = _verify(client, _latest_code(client))

    assert response.status_code == 200
    assert response.json()["email"] is None
    assert response.json()["phone_number"] == NORMALIZED_PHONE
    assert "fitsho_session" in response.cookies
    user = db.scalar(select(User).where(User.phone_number == NORMALIZED_PHONE))
    assert user is not None
    assert user.password_hash is None
    assert client.get("/api/v1/auth/me").json()["id"] == str(user.id)


def test_send_response_does_not_reveal_whether_phone_user_exists(client: TestClient) -> None:
    _send(client)
    _verify(client, _latest_code(client))
    client.post("/api/v1/auth/logout", headers=ORIGIN)
    client.app.state.sms_provider.deliveries.clear()

    existing = _send(client, PHONE)
    new = _send(client, "09351234567")

    assert existing.status_code == new.status_code == 202
    assert existing.json() == new.json()
    assert len(client.app.state.sms_provider.deliveries) == 2


def test_phone_otp_rejects_invalid_phone_and_untrusted_origin(client: TestClient) -> None:
    invalid = _send(client, "02112345678")
    untrusted_send = client.post(
        "/api/v1/auth/phone/send-otp",
        json={"phone_number": PHONE},
    )
    untrusted_verify = client.post(
        "/api/v1/auth/phone/verify-otp",
        json={"phone_number": PHONE, "code": "123456"},
    )

    assert invalid.status_code == 422
    assert untrusted_send.status_code == untrusted_verify.status_code == 403
