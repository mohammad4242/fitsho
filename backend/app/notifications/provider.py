from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

NotificationProviderName = Literal["fcm", "apns"]
NotificationOutcomeKind = Literal["sent", "retryable", "invalid_token", "permanent"]


@dataclass(frozen=True)
class NotificationSendOutcome:
    kind: NotificationOutcomeKind
    error_code: str | None = None
    provider_message_id: str | None = None

    @classmethod
    def sent(cls, provider_message_id: str) -> NotificationSendOutcome:
        return cls(kind="sent", provider_message_id=provider_message_id)

    @classmethod
    def retryable(cls, error_code: str) -> NotificationSendOutcome:
        return cls(kind="retryable", error_code=error_code)

    @classmethod
    def invalid_token(cls, error_code: str) -> NotificationSendOutcome:
        return cls(kind="invalid_token", error_code=error_code)

    @classmethod
    def permanent(cls, error_code: str) -> NotificationSendOutcome:
        return cls(kind="permanent", error_code=error_code)


class NotificationProvider(Protocol):
    def send(
        self,
        *,
        token_value: str,
        event_type: str,
        payload: dict[str, object],
    ) -> NotificationSendOutcome: ...
