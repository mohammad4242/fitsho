from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlsplit
from uuid import UUID

from ..schemas import AgentName
from .base import ParsedAuthUpdate
from .schemas import (
    AuthSafeErrorMessage,
    AuthSessionStatus,
    AuthSessionView,
)

if TYPE_CHECKING:
    from .process import AuthProcess


_TERMINAL_STATUSES = frozenset(
    {
        AuthSessionStatus.AUTHENTICATED,
        AuthSessionStatus.FAILED,
        AuthSessionStatus.CANCELED,
        AuthSessionStatus.EXPIRED,
    }
)


@dataclass
class AuthSession:
    session_id: UUID
    agent: AgentName
    expires_at: datetime
    status: AuthSessionStatus = AuthSessionStatus.STARTING
    verification_url: str | None = None
    user_code: str | None = None
    input_label: str | None = None
    safe_error_message: str | None = None
    process: AuthProcess | None = field(default=None, repr=False, compare=False)

    @property
    def is_terminal(self) -> bool:
        return self.status in _TERMINAL_STATUSES

    @property
    def is_active(self) -> bool:
        return not self.is_terminal

    def view(self) -> AuthSessionView:
        return AuthSessionView(
            session_id=self.session_id,
            agent=self.agent,
            status=self.status,
            verification_url=self.verification_url,
            user_code=self.user_code,
            input_label=self.input_label,
            expires_at=self.expires_at,
            safe_error_message=self.safe_error_message,
        )

    def apply_update(self, update: ParsedAuthUpdate, *, allowed_hosts: frozenset[str]) -> None:
        if self.is_terminal:
            return
        verification_url = self.verification_url
        user_code = self.user_code
        input_label = self.input_label
        safe_error_message = self.safe_error_message

        if update.verification_url is not None:
            self._validate_allowed_url(update.verification_url, allowed_hosts)
            verification_url = update.verification_url
        if update.user_code is not None:
            user_code = update.user_code
        if update.input_label is not None:
            input_label = update.input_label
        if update.safe_error_message is not None:
            safe_error_message = update.safe_error_message

        next_status = self.status
        if update.failed or update.safe_error_message is not None:
            next_status = AuthSessionStatus.FAILED
            safe_error_message = safe_error_message or AuthSafeErrorMessage.FAILED.value
        elif update.authenticated:
            next_status = AuthSessionStatus.AUTHENTICATED
            safe_error_message = None
        elif self.status is AuthSessionStatus.VERIFYING:
            next_status = AuthSessionStatus.VERIFYING
            input_label = None
        elif update.needs_input:
            if input_label is None:
                raise ValueError("authentication input label is required")
            next_status = AuthSessionStatus.WAITING_FOR_INPUT
        elif update.verification_url is not None or update.user_code is not None:
            next_status = AuthSessionStatus.WAITING_FOR_USER

        candidate = AuthSessionView(
            session_id=self.session_id,
            agent=self.agent,
            status=next_status,
            verification_url=verification_url,
            user_code=user_code,
            input_label=input_label,
            expires_at=self.expires_at,
            safe_error_message=safe_error_message,
        )
        self.status = candidate.status
        self.verification_url = candidate.verification_url
        self.user_code = candidate.user_code
        self.input_label = candidate.input_label
        self.safe_error_message = candidate.safe_error_message
        if self.is_terminal:
            self._clear_public_handoff()

    def mark_verifying(self) -> None:
        if self.is_active:
            self.status = AuthSessionStatus.VERIFYING
            self.input_label = None

    def mark_terminal(
        self,
        status: AuthSessionStatus,
        safe_error_message: str | None = None,
    ) -> None:
        if status not in _TERMINAL_STATUSES:
            raise ValueError("status must be terminal")
        if self.is_terminal:
            return
        if status is AuthSessionStatus.AUTHENTICATED:
            safe_error_message = None
        elif safe_error_message is None:
            safe_error_message = {
                AuthSessionStatus.FAILED: AuthSafeErrorMessage.FAILED.value,
                AuthSessionStatus.CANCELED: AuthSafeErrorMessage.CANCELED.value,
                AuthSessionStatus.EXPIRED: AuthSafeErrorMessage.EXPIRED.value,
            }[status]
        candidate = AuthSessionView(
            session_id=self.session_id,
            agent=self.agent,
            status=status,
            expires_at=self.expires_at,
            safe_error_message=safe_error_message,
        )
        self.status = candidate.status
        self.safe_error_message = candidate.safe_error_message
        self._clear_public_handoff()

    def _clear_public_handoff(self) -> None:
        self.verification_url = None
        self.user_code = None
        self.input_label = None

    @staticmethod
    def _validate_allowed_url(url: str, allowed_hosts: frozenset[str]) -> None:
        try:
            parsed = urlsplit(url)
            hostname = parsed.hostname
            port = parsed.port
        except ValueError as exc:
            raise ValueError("verification URL is invalid") from exc
        if (
            parsed.scheme.lower() != "https"
            or hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or (port is not None and not 1 <= port <= 65535)
        ):
            raise ValueError("verification URL shape is unsafe")
        if hostname.lower() not in {host.lower() for host in allowed_hosts}:
            raise ValueError("verification URL hostname is not allowlisted")
