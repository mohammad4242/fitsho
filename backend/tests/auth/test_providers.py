from types import TracebackType
from typing import Any

import httpx
import pytest

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


def test_kavenegar_provider_uses_official_send_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(httpx, "Client", FakeHttpClient)
    provider = KavenegarSmsProvider(
        Settings(
            sms_provider="kavenegar",
            kavenegar_api_key="api-key",
            kavenegar_sender="10004346",
        )
    )

    provider.send_login_otp("+989123456789", "123456")

    assert FakeHttpClient.request_url == "https://api.kavenegar.com/v1/api-key/sms/send.json"
    assert FakeHttpClient.request_data == {
        "receptor": "+989123456789",
        "message": "کد ورود فیتشو: 123456",
        "sender": "10004346",
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
