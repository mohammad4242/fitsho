from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal, Protocol
from urllib.parse import quote

import httpx
from google.auth.credentials import Credentials
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from app.config import Settings

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
FcmOutcomeKind = Literal["sent", "retryable", "invalid_token", "permanent"]


@dataclass(frozen=True)
class FcmSendOutcome:
    kind: FcmOutcomeKind
    error_code: str | None = None
    provider_message_id: str | None = None

    @classmethod
    def sent(cls, provider_message_id: str) -> FcmSendOutcome:
        return cls(kind="sent", provider_message_id=provider_message_id)

    @classmethod
    def retryable(cls, error_code: str) -> FcmSendOutcome:
        return cls(kind="retryable", error_code=error_code)

    @classmethod
    def invalid_token(cls, error_code: str) -> FcmSendOutcome:
        return cls(kind="invalid_token", error_code=error_code)

    @classmethod
    def permanent(cls, error_code: str) -> FcmSendOutcome:
        return cls(kind="permanent", error_code=error_code)


class NotificationProvider(Protocol):
    def send(
        self,
        *,
        token_value: str,
        event_type: str,
        payload: dict[str, object],
    ) -> FcmSendOutcome: ...


class FcmConfigurationError(Exception):
    pass


class FcmProvider:
    def __init__(
        self,
        *,
        project_id: str,
        credentials: Credentials,
        client: httpx.Client,
        base_url: str = "https://fcm.googleapis.com",
    ) -> None:
        self._project_id = project_id
        self._credentials = credentials
        self._client = client
        self._base_url = base_url.rstrip("/")

    def send(
        self,
        *,
        token_value: str,
        event_type: str,
        payload: dict[str, object],
    ) -> FcmSendOutcome:
        access_token = self._access_token()
        if access_token is None:
            return FcmSendOutcome.permanent("AUTH_TOKEN_UNAVAILABLE")
        try:
            response = self._client.post(
                f"{self._base_url}/v1/projects/{quote(self._project_id, safe='')}/messages:send",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={"message": _message(event_type, token_value, payload)},
            )
        except httpx.RequestError:
            return FcmSendOutcome.retryable("NETWORK_ERROR")
        return _classify_response(response)

    def close(self) -> None:
        self._client.close()

    def _access_token(self) -> str | None:
        try:
            if self._credentials.token is None or self._credentials.expired:
                self._credentials.refresh(Request())  # type: ignore[no-untyped-call]
        except (GoogleAuthError, ValueError):
            return None
        token = self._credentials.token
        return token if isinstance(token, str) and token else None


def build_fcm_provider(settings: Settings) -> FcmProvider | None:
    if not settings.notification_fcm_enabled:
        return None
    secret = settings.notification_fcm_service_account_json
    if secret is None:
        raise FcmConfigurationError("FCM service account configuration is missing")
    try:
        info = json.loads(secret.get_secret_value())
        if not isinstance(info, dict):
            raise ValueError
        project_id = settings.notification_fcm_project_id or info.get("project_id")
        if not isinstance(project_id, str) or not project_id.strip():
            raise ValueError
        credentials = service_account.Credentials.from_service_account_info(  # type: ignore[no-untyped-call]
            info,
            scopes=[FCM_SCOPE],
        )
    except (GoogleAuthError, TypeError, ValueError, json.JSONDecodeError, KeyError):
        raise FcmConfigurationError("FCM service account configuration is invalid") from None
    return FcmProvider(
        project_id=project_id.strip(),
        credentials=credentials,
        client=httpx.Client(
            timeout=settings.notification_fcm_timeout_seconds,
            trust_env=False,
        ),
        base_url=settings.notification_fcm_base_url,
    )


def _message(event_type: str, token_value: str, payload: dict[str, object]) -> dict[str, object]:
    data: dict[str, str] = {"event_type": event_type}
    for key, value in payload.items():
        if key in {"title", "body"}:
            continue
        if isinstance(value, (str, int, float, bool)):
            data[key] = str(value)
        elif key == "data" and isinstance(value, dict):
            for nested_key, nested_value in value.items():
                if isinstance(nested_value, (str, int, float, bool)):
                    data[str(nested_key)] = str(nested_value)
    title = payload.get("title")
    body = payload.get("body")
    return {
        "token": token_value,
        "notification": {
            "title": title if isinstance(title, str) and title else "Fitician",
            "body": body if isinstance(body, str) and body else "You have a new Fitician update.",
        },
        "data": data,
    }


def _classify_response(response: httpx.Response) -> FcmSendOutcome:
    try:
        body = response.json()
    except ValueError:
        body = {}
    if 200 <= response.status_code < 300:
        message_name = body.get("name") if isinstance(body, dict) else None
        if isinstance(message_name, str) and message_name:
            return FcmSendOutcome.sent(message_name)
        return FcmSendOutcome.permanent("MALFORMED_RESPONSE")

    error_code = _error_code(body) or f"HTTP_{response.status_code}"
    if error_code in {"UNREGISTERED", "INVALID_ARGUMENT"}:
        return FcmSendOutcome.invalid_token(error_code)
    if response.status_code in {408, 425, 429} or response.status_code >= 500:
        return FcmSendOutcome.retryable(error_code)
    return FcmSendOutcome.permanent(error_code)


def _error_code(body: object) -> str | None:
    if not isinstance(body, dict):
        return None
    error = body.get("error")
    if not isinstance(error, dict):
        return None
    details = error.get("details")
    if isinstance(details, list):
        for detail in details:
            if isinstance(detail, dict) and isinstance(detail.get("errorCode"), str):
                return _safe_error_code(detail["errorCode"])
    if isinstance(error.get("status"), str):
        return _safe_error_code(error["status"])
    return None


def _safe_error_code(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value).upper()[:64] or "PROVIDER_ERROR"
