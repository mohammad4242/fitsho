from __future__ import annotations

import base64
import json
import re
import time
from collections.abc import Callable
from threading import Lock
from urllib.parse import quote, urlsplit

import httpx
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from app.config import Settings

from .provider import NotificationSendOutcome

ApnsSendOutcome = NotificationSendOutcome


class ApnsConfigurationError(Exception):
    pass


class ApnsProvider:
    def __init__(
        self,
        *,
        team_id: str,
        key_id: str,
        bundle_id: str,
        private_key: ec.EllipticCurvePrivateKey,
        client: httpx.Client,
        base_url: str = "https://api.push.apple.com",
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not isinstance(private_key.curve, ec.SECP256R1):
            raise ValueError("APNs private key must use P-256")
        self._team_id = team_id
        self._key_id = key_id
        self._bundle_id = bundle_id
        self._private_key = private_key
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._clock = clock
        self._jwt_lock = Lock()
        self._jwt: str | None = None
        self._jwt_issued_at: int | None = None

    def send(
        self,
        *,
        token_value: str,
        event_type: str,
        payload: dict[str, object],
    ) -> ApnsSendOutcome:
        try:
            response = self._client.post(
                f"{self._base_url}/3/device/{quote(token_value, safe='')}",
                headers={
                    "Authorization": f"Bearer {self._authorization_token()}",
                    "apns-topic": self._bundle_id,
                    "apns-push-type": "alert",
                    "apns-priority": "10",
                    "Content-Type": "application/json",
                },
                json=_message(event_type, payload),
            )
        except httpx.RequestError:
            return ApnsSendOutcome.retryable("NETWORK_ERROR")
        return _classify_response(response)

    def close(self) -> None:
        self._client.close()

    def _authorization_token(self) -> str:
        now = int(self._clock())
        with self._jwt_lock:
            if self._jwt is not None and self._jwt_issued_at is not None:
                if now >= self._jwt_issued_at and now - self._jwt_issued_at < 50 * 60:
                    return self._jwt
            header = _base64url_json({"alg": "ES256", "kid": self._key_id, "typ": "JWT"})
            claims = _base64url_json({"iss": self._team_id, "iat": now})
            signing_input = f"{header}.{claims}".encode("ascii")
            der_signature = self._private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
            r, s = decode_dss_signature(der_signature)
            signature = base64.urlsafe_b64encode(
                r.to_bytes(32, "big") + s.to_bytes(32, "big")
            ).rstrip(b"=").decode("ascii")
            self._jwt = f"{header}.{claims}.{signature}"
            self._jwt_issued_at = now
            return self._jwt


def build_apns_provider(settings: Settings) -> ApnsProvider | None:
    if not settings.notification_apns_enabled:
        return None
    team_id = _required(settings.notification_apns_team_id)
    key_id = _required(settings.notification_apns_key_id)
    bundle_id = _required(settings.notification_apns_bundle_id)
    secret = settings.notification_apns_private_key
    if team_id is None or key_id is None or bundle_id is None or secret is None:
        raise ApnsConfigurationError("APNs provider configuration is missing")
    if urlsplit(settings.notification_apns_base_url).scheme != "https":
        raise ApnsConfigurationError("APNs provider requires an HTTPS base URL")
    try:
        pem = secret.get_secret_value().replace("\\n", "\n").encode("utf-8")
        loaded = serialization.load_pem_private_key(pem, password=None)
    except (TypeError, ValueError, UnsupportedAlgorithm):
        raise ApnsConfigurationError("APNs private key configuration is invalid") from None
    if not isinstance(loaded, ec.EllipticCurvePrivateKey) or not isinstance(
        loaded.curve, ec.SECP256R1
    ):
        raise ApnsConfigurationError("APNs private key must use P-256")
    return ApnsProvider(
        team_id=team_id,
        key_id=key_id,
        bundle_id=bundle_id,
        private_key=loaded,
        client=httpx.Client(
            timeout=settings.notification_apns_timeout_seconds,
            trust_env=False,
            http2=True,
        ),
        base_url=settings.notification_apns_base_url,
    )


def _required(value: str | None) -> str | None:
    normalized = value.strip() if value is not None else ""
    return normalized or None


def _base64url_json(value: dict[str, object]) -> str:
    encoded = json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).rstrip(b"=").decode("ascii")


def _message(event_type: str, payload: dict[str, object]) -> dict[str, object]:
    title = payload.get("title")
    body = payload.get("body")
    message: dict[str, object] = {
        "aps": {
            "alert": {
                "title": title if isinstance(title, str) and title else "Fitician",
                "body": body
                if isinstance(body, str) and body
                else "You have a new Fitician update.",
            },
            "sound": "default",
        },
    }
    data: dict[str, str] = {"event_type": event_type}
    for key, value in payload.items():
        if key in {"title", "body", "channel_id"}:
            continue
        if isinstance(value, (str, int, float, bool)):
            data[key] = str(value)
        elif key == "data" and isinstance(value, dict):
            for nested_key, nested_value in value.items():
                if isinstance(nested_value, (str, int, float, bool)):
                    data[str(nested_key)] = str(nested_value)
    message.update(data)
    return message


def _classify_response(response: httpx.Response) -> ApnsSendOutcome:
    try:
        body = response.json()
    except ValueError:
        body = {}
    if 200 <= response.status_code < 300:
        provider_message_id = response.headers.get("apns-id") or "accepted"
        return ApnsSendOutcome.sent(provider_message_id)

    reason = body.get("reason") if isinstance(body, dict) else None
    error_code = _safe_error_code(reason) if isinstance(reason, str) else None
    error_code = error_code or f"HTTP_{response.status_code}"
    if response.status_code == 410 or error_code in {
        "BADDEVICETOKEN",
        "DEVICETOKENNOTFORTOPIC",
        "UNREGISTERED",
    }:
        return ApnsSendOutcome.invalid_token(error_code)
    if response.status_code in {408, 425, 429} or response.status_code >= 500 or error_code in {
        "SHUTDOWN",
        "SERVICENOTAVAILABLE",
        "TOOMANYREQUESTS",
    }:
        return ApnsSendOutcome.retryable(error_code)
    return ApnsSendOutcome.permanent(error_code)


def _safe_error_code(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value).upper()[:64] or "PROVIDER_ERROR"
