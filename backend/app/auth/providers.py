import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

import httpx

from app.config import Settings


class EmailProvider(Protocol):
    def send_password_reset(self, recipient: str, reset_url: str) -> None: ...


class SmsProvider(Protocol):
    def send_login_otp(self, phone_number: str, code: str) -> None: ...


@dataclass(frozen=True)
class PasswordResetDelivery:
    recipient: str
    reset_url: str


class FakeEmailProvider:
    def __init__(self) -> None:
        self.deliveries: list[PasswordResetDelivery] = []

    def send_password_reset(self, recipient: str, reset_url: str) -> None:
        self.deliveries.append(PasswordResetDelivery(recipient=recipient, reset_url=reset_url))


@dataclass(frozen=True)
class OtpDelivery:
    phone_number: str
    code: str


class FakeSmsProvider:
    def __init__(self) -> None:
        self.deliveries: list[OtpDelivery] = []

    def send_login_otp(self, phone_number: str, code: str) -> None:
        self.deliveries.append(OtpDelivery(phone_number=phone_number, code=code))


class SmtpEmailProvider:
    def __init__(self, settings: Settings) -> None:
        if settings.smtp_host is None or settings.smtp_from_address is None:
            raise ValueError("SMTP provider is not configured")
        self._host = settings.smtp_host
        self._port = settings.smtp_port
        self._username = settings.smtp_username
        self._password = (
            settings.smtp_password.get_secret_value()
            if settings.smtp_password is not None
            else None
        )
        self._from_address = settings.smtp_from_address
        self._use_tls = settings.smtp_use_tls

    def send_password_reset(self, recipient: str, reset_url: str) -> None:
        message = EmailMessage()
        message["From"] = self._from_address
        message["To"] = recipient
        message["Subject"] = "بازنشانی رمز عبور فیتشو"
        message.set_content(
            "برای انتخاب رمز عبور جدید، لینک زیر را باز کنید:\n\n"
            f"{reset_url}\n\nاگر این درخواست را ثبت نکرده‌اید، این پیام را نادیده بگیرید."
        )
        with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username is not None and self._password is not None:
                smtp.login(self._username, self._password)
            smtp.send_message(message)


class KavenegarSmsProvider:
    def __init__(self, settings: Settings) -> None:
        if settings.kavenegar_api_key is None:
            raise ValueError("Kavenegar provider is not configured")
        api_key = settings.kavenegar_api_key.get_secret_value()
        base_url = settings.kavenegar_base_url.rstrip("/")
        self._url = f"{base_url}/{api_key}/sms/send.json"
        self._sender = settings.kavenegar_sender
        self._timeout = settings.sms_timeout_seconds

    def send_login_otp(self, phone_number: str, code: str) -> None:
        payload = {
            "receptor": phone_number,
            "message": f"کد ورود فیتشو: {code}",
        }
        if self._sender is not None:
            payload["sender"] = self._sender
        with httpx.Client(timeout=self._timeout, trust_env=False) as client:
            response = client.post(self._url, data=payload)
            response.raise_for_status()


def build_email_provider(settings: Settings) -> EmailProvider:
    if settings.email_provider == "smtp":
        return SmtpEmailProvider(settings)
    return FakeEmailProvider()


def build_sms_provider(settings: Settings) -> SmsProvider:
    if settings.sms_provider == "kavenegar":
        return KavenegarSmsProvider(settings)
    return FakeSmsProvider()
