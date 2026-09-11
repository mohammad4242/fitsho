import base64
import binascii
import hmac
import json
import smtplib
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
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
class AppleIdentity:
    sub: str
    email: str | None
    email_verified: bool
    name: str | None
    picture: str | None


class AppleIdentityProvider(Protocol):
    def verify(self, credential: str, nonce: str) -> AppleIdentity: ...


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
            try:
                body = response.json()
            except ValueError:
                raise RuntimeError("Kavenegar delivery failed") from None
            result = body.get("return") if isinstance(body, dict) else None
            if not isinstance(result, dict) or result.get("status") != 200:
                raise RuntimeError("Kavenegar delivery failed")


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


AppleJwks = Mapping[str, Mapping[str, str]]
AppleJwksFetcher = Callable[[], AppleJwks]


def _decode_base64url(value: str) -> bytes:
    try:
        encoded = value.encode("ascii")
        return base64.b64decode(encoded + b"=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
    except (UnicodeEncodeError, binascii.Error, ValueError):
        raise ValueError("Invalid Apple token encoding") from None


def _decode_json_segment(value: str) -> dict[str, object]:
    try:
        decoded = json.loads(_decode_base64url(value))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("Invalid Apple token claims") from None
    if not isinstance(decoded, dict):
        raise ValueError("Invalid Apple token claims")
    return decoded


def _claim_string(claims: Mapping[str, object], name: str) -> str | None:
    value = claims.get(name)
    return value if isinstance(value, str) else None


def _claim_timestamp(claims: Mapping[str, object], name: str) -> float | None:
    value = claims.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _claim_audience_matches(claims: Mapping[str, object], expected: str) -> bool:
    audience = claims.get("aud")
    if isinstance(audience, str):
        return audience == expected
    if isinstance(audience, list):
        return expected in audience and all(isinstance(item, str) for item in audience)
    return False


def _apple_email_verified(claims: Mapping[str, object]) -> bool:
    value = claims.get("email_verified")
    if isinstance(value, bool):
        return value
    return isinstance(value, str) and value.casefold() == "true"


def _rsa_public_key(jwk: Mapping[str, str]) -> RSAPublicKey:
    try:
        if jwk.get("kty") != "RSA" or jwk.get("alg") != "RS256":
            raise ValueError("Invalid Apple signing key")
        modulus = int.from_bytes(_decode_base64url(jwk["n"]), "big")
        exponent = int.from_bytes(_decode_base64url(jwk["e"]), "big")
    except (KeyError, TypeError, ValueError):
        raise ValueError("Invalid Apple signing key") from None
    if modulus <= 0 or exponent <= 0:
        raise ValueError("Invalid Apple signing key")
    try:
        return rsa.RSAPublicNumbers(exponent, modulus).public_key()
    except ValueError:
        raise ValueError("Invalid Apple signing key") from None


class AppleIdTokenProvider:
    def __init__(
        self,
        settings: Settings,
        *,
        jwks_fetcher: AppleJwksFetcher | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._client_id = settings.apple_client_id
        self._jwks_url = settings.apple_jwks_url
        self._jwks_cache_ttl_seconds = settings.apple_jwks_cache_ttl_seconds
        self._timeout_seconds = settings.apple_jwks_timeout_seconds
        self._clock_skew_seconds = settings.apple_clock_skew_seconds
        self._clock = clock
        self._jwks_fetcher = jwks_fetcher or self._fetch_jwks
        self._jwks_cache: AppleJwks | None = None
        self._jwks_cached_at = 0.0
        self._jwks_lock = threading.Lock()

    def _fetch_jwks(self) -> AppleJwks:
        try:
            with httpx.Client(timeout=self._timeout_seconds, trust_env=False) as client:
                response = client.get(self._jwks_url)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError):
            raise ValueError("Apple signing keys unavailable") from None
        keys = payload.get("keys") if isinstance(payload, dict) else None
        if not isinstance(keys, list):
            raise ValueError("Apple signing keys unavailable")
        result: dict[str, Mapping[str, str]] = {}
        for key in keys:
            if not isinstance(key, dict):
                continue
            kid = key.get("kid")
            if not isinstance(kid, str):
                continue
            if not all(isinstance(value, str) for value in key.values()):
                continue
            result[kid] = key
        if not result:
            raise ValueError("Apple signing keys unavailable")
        return result

    def _get_jwks(self, *, force_refresh: bool = False) -> AppleJwks:
        now = self._clock()
        with self._jwks_lock:
            if (
                not force_refresh
                and self._jwks_cache is not None
                and now - self._jwks_cached_at < self._jwks_cache_ttl_seconds
            ):
                return self._jwks_cache
            jwks = self._jwks_fetcher()
            self._jwks_cache = dict(jwks)
            self._jwks_cached_at = now
            return self._jwks_cache

    def verify(self, credential: str, nonce: str) -> AppleIdentity:
        if self._client_id is None:
            raise ValueError("Apple identity is not configured")
        if not credential or not nonce:
            raise ValueError("Apple identity credential is incomplete")
        parts = credential.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid Apple identity credential")
        header = _decode_json_segment(parts[0])
        claims = _decode_json_segment(parts[1])
        signature = _decode_base64url(parts[2])
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
            raise ValueError("Invalid Apple identity header")

        key_id = header["kid"]
        assert isinstance(key_id, str)
        jwk = self._get_jwks().get(key_id)
        if jwk is None:
            jwk = self._get_jwks(force_refresh=True).get(key_id)
        if jwk is None:
            raise ValueError("Apple signing key unavailable")
        public_key = _rsa_public_key(jwk)
        signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
        try:
            public_key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA256())
        except (InvalidSignature, ValueError):
            raise ValueError("Invalid Apple identity signature") from None

        if claims.get("iss") != "https://appleid.apple.com":
            raise ValueError("Invalid Apple token issuer")
        if not _claim_audience_matches(claims, self._client_id):
            raise ValueError("Invalid Apple token audience")
        expires_at = _claim_timestamp(claims, "exp")
        if expires_at is None or self._clock() > expires_at + self._clock_skew_seconds:
            raise ValueError("Expired Apple identity token")
        issued_at = _claim_timestamp(claims, "iat")
        if issued_at is not None and issued_at > self._clock() + self._clock_skew_seconds:
            raise ValueError("Apple identity token is not active")
        token_nonce = _claim_string(claims, "nonce")
        if token_nonce is None or not hmac.compare_digest(token_nonce, nonce):
            raise ValueError("Invalid Apple token nonce")
        subject = _claim_string(claims, "sub")
        if subject is None or not subject or len(subject) > 255:
            raise ValueError("Apple token has no valid subject")
        email = _claim_string(claims, "email")
        if email is not None and len(email) > 320:
            email = None
        return AppleIdentity(
            sub=subject,
            email=email,
            email_verified=_apple_email_verified(claims),
            name=None,
            picture=None,
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


def build_apple_identity_provider(settings: Settings) -> AppleIdentityProvider:
    return AppleIdTokenProvider(settings)
