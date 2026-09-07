import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

import httpx
from google.auth.transport import requests as google_auth_requests
from google.oauth2 import id_token as google_id_token

from app.config import Settings


class EmailProvider(Protocol):
    def send_password_reset(self, recipient: str, reset_url: str) -> None: ...

    def send_email_verification(self, recipient: str, verification_url: str) -> None: ...

    def send_welcome_email(self, recipient: str) -> None: ...


class SmsProvider(Protocol):
    def send_login_otp(self, phone_number: str, code: str) -> None: ...


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str | None
    email_verified: bool
    name: str | None
    picture: str | None


class GoogleIdentityProvider(Protocol):
    def verify(self, credential: str) -> GoogleIdentity: ...


@dataclass(frozen=True)
class PasswordResetDelivery:
    recipient: str
    reset_url: str


@dataclass(frozen=True)
class EmailVerificationDelivery:
    recipient: str
    verification_url: str


@dataclass(frozen=True)
class WelcomeEmailDelivery:
    recipient: str


class FakeEmailProvider:
    def __init__(self) -> None:
        self.deliveries: list[PasswordResetDelivery] = []
        self.verification_deliveries: list[EmailVerificationDelivery] = []
        self.welcome_deliveries: list[WelcomeEmailDelivery] = []

    def send_password_reset(self, recipient: str, reset_url: str) -> None:
        self.deliveries.append(PasswordResetDelivery(recipient=recipient, reset_url=reset_url))

    def send_email_verification(self, recipient: str, verification_url: str) -> None:
        self.verification_deliveries.append(
            EmailVerificationDelivery(recipient=recipient, verification_url=verification_url)
        )

    def send_welcome_email(self, recipient: str) -> None:
        self.welcome_deliveries.append(WelcomeEmailDelivery(recipient=recipient))


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

    def _send(self, recipient: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self._from_address
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        with smtplib.SMTP(self._host, self._port, timeout=10) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username is not None and self._password is not None:
                smtp.login(self._username, self._password)
            smtp.send_message(message)

    def send_password_reset(self, recipient: str, reset_url: str) -> None:
        self._send(
            recipient,
            "بازنشانی رمز عبور فیتشو",
            "برای انتخاب رمز عبور جدید، لینک زیر را باز کنید:\n\n"
            f"{reset_url}\n\n"
            "اگر این درخواست را ثبت نکرده‌اید، این پیام را نادیده بگیرید.",
        )

    def send_email_verification(self, recipient: str, verification_url: str) -> None:
        self._send(
            recipient,
            "تأیید ایمیل فیتشو",
            "برای تأیید نشانی ایمیل خود، لینک زیر را باز کنید:\n\n"
            f"{verification_url}\n\n"
            "اگر در فیتشو ثبت‌نام نکرده‌اید، این پیام را نادیده بگیرید.",
        )

    def send_welcome_email(self, recipient: str) -> None:
        self._send(
            recipient,
            "به فیتشو خوش آمدید",
            "ایمیل شما با موفقیت تأیید شد. به فیتشو خوش آمدید.",
        )


class KavenegarSmsProvider:
    def __init__(self, settings: Settings) -> None:
        if settings.kavenegar_api_key is None:
            raise ValueError("Kavenegar provider is not configured")
        api_key = settings.kavenegar_api_key.get_secret_value()
        base_url = settings.kavenegar_base_url.rstrip("/")
        self._url = f"{base_url}/{api_key}/verify/lookup.json"
        self._template = settings.kavenegar_verify_template
        self._timeout = settings.sms_timeout_seconds

    def send_login_otp(self, phone_number: str, code: str) -> None:
        payload = {
            "receptor": phone_number,
            "token": code,
            "template": self._template,
        }
        with httpx.Client(timeout=self._timeout, trust_env=False) as client:
            response = client.post(self._url, data=payload)
            response.raise_for_status()


class GoogleIdTokenProvider:
    def __init__(self, settings: Settings) -> None:
        self._client_id = settings.google_client_id

    def verify(self, credential: str) -> GoogleIdentity:
        if self._client_id is None:
            raise ValueError("Google identity is not configured")
        claims = google_id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
            credential,
            google_auth_requests.Request(),
            self._client_id,
        )
        issuer = claims.get("iss")
        if issuer not in {"accounts.google.com", "https://accounts.google.com"}:
            raise ValueError("Invalid Google token issuer")
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject or len(subject) > 255:
            raise ValueError("Google token has no valid subject")
        email_claim = claims.get("email")
        email = email_claim if isinstance(email_claim, str) and len(email_claim) <= 320 else None
        name_claim = claims.get("name")
        picture_claim = claims.get("picture")
        return GoogleIdentity(
            sub=subject,
            email=email,
            email_verified=claims.get("email_verified") is True,
            name=name_claim if isinstance(name_claim, str) else None,
            picture=picture_claim if isinstance(picture_claim, str) else None,
        )


def build_email_provider(settings: Settings) -> EmailProvider:
    if settings.email_provider == "smtp":
        return SmtpEmailProvider(settings)
    return FakeEmailProvider()


def build_sms_provider(settings: Settings) -> SmsProvider:
    if settings.sms_provider == "kavenegar":
        return KavenegarSmsProvider(settings)
    return FakeSmsProvider()


def build_google_identity_provider(settings: Settings) -> GoogleIdentityProvider:
    return GoogleIdTokenProvider(settings)
