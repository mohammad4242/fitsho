from types import TracebackType
from typing import Any

import httpx
import pytest

from app.auth import providers
from app.auth.providers import KavenegarSmsProvider, SmtpEmailProvider
from app.config import Settings


class FakeHttpClient:
    request_url: str | None = None
    request_data: dict[str, str] | None = None

    def __init__(self, **_kwargs: object) -> None:
        pass

    def __enter__(self) -> "FakeHttpClient":
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        pass

    def post(self, url: str, *, data: dict[str, str]) -> httpx.Response:
        type(self).request_url = url
        type(self).request_data = data
        return httpx.Response(200, request=httpx.Request("POST", url))


def test_kavenegar_provider_uses_verification_template_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "Client", FakeHttpClient)
    provider = KavenegarSmsProvider(
        Settings(
            sms_provider="kavenegar",
            kavenegar_api_key="api-key",
            kavenegar_sender="10004346",
            kavenegar_verify_template="fitsho-login",
        )
    )

    provider.send_login_otp("+989123456789", "123456")

    assert FakeHttpClient.request_url == "https://api.kavenegar.com/v1/api-key/verify/lookup.json"
    assert FakeHttpClient.request_data == {
        "receptor": "+989123456789",
        "token": "123456",
        "template": "fitsho-login",
    }


class FakeSmtp:
    last_message: Any = None

    def __init__(self, host: str, port: int, timeout: int) -> None:
        assert (host, port, timeout) == ("smtp.example.com", 587, 10)

    def __enter__(self) -> "FakeSmtp":
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        pass

    def starttls(self) -> None:
        pass

    def login(self, username: str, password: str) -> None:
        assert (username, password) == ("fitsho", "smtp-secret")

    def send_message(self, message: Any) -> None:
        type(self).last_message = message


def test_smtp_provider_sends_reset_link_without_exposing_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("smtplib.SMTP", FakeSmtp)
    provider = SmtpEmailProvider(
        Settings(
            email_provider="smtp",
            smtp_host="smtp.example.com",
            smtp_username="fitsho",
            smtp_password="smtp-secret",
            smtp_from_address="no-reply@fitsho.example",
        )
    )

    provider.send_password_reset(
        "user@example.com",
        "https://fitsho.example/reset-password?token=raw-token",
    )

    message = FakeSmtp.last_message
    assert message["To"] == "user@example.com"
    assert "raw-token" in message.get_content()
    assert "smtp-secret" not in message.as_string()


def test_smtp_provider_reuses_delivery_for_verification_and_welcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("smtplib.SMTP", FakeSmtp)
    provider = SmtpEmailProvider(
        Settings(
            email_provider="smtp",
            smtp_host="smtp.example.com",
            smtp_from_address="no-reply@fitsho.example",
        )
    )

    provider.send_email_verification(
        "user@example.com",
        "https://fitsho.example/verify-email?token=verification-token",
    )
    assert "verification-token" in FakeSmtp.last_message.get_content()
    provider.send_welcome_email("user@example.com")
    assert "فیتشو" in FakeSmtp.last_message.get_content()


def test_google_provider_passes_backend_audience_to_official_verifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_verify(token: str, _request: object, audience: str) -> dict[str, object]:
        captured.update(token=token, audience=audience)
        return {
            "iss": "https://accounts.google.com",
            "sub": "google-sub",
            "email": "member@example.com",
            "email_verified": True,
            "name": "Member",
            "picture": "https://example.com/picture.jpg",
        }

    monkeypatch.setattr("google.oauth2.id_token.verify_oauth2_token", fake_verify)
    assert hasattr(providers, "GoogleIdTokenProvider")
    provider = providers.GoogleIdTokenProvider(Settings(google_client_id="fitsho-client-id"))

    identity = provider.verify("signed-token")

    assert captured == {"token": "signed-token", "audience": "fitsho-client-id"}
    assert identity.sub == "google-sub"
    assert identity.email_verified is True
