from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.auth.base import ParsedAuthUpdate
from app.auth.schemas import AuthSessionStatus
from app.auth.session import AuthSession
from app.schemas import AgentName


def make_session() -> AuthSession:
    return AuthSession(
        session_id=uuid4(),
        agent=AgentName.CODEX,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )


def test_session_update_exposes_only_allowlisted_auth_fields() -> None:
    session = make_session()
    session.apply_update(
        ParsedAuthUpdate(
            verification_url="https://auth.openai.com/device?state=opaque",
            user_code="ABCD-EFGH",
        ),
        allowed_hosts=frozenset({"auth.openai.com"}),
    )

    view = session.view()
    assert view.status is AuthSessionStatus.WAITING_FOR_USER
    assert view.verification_url == "https://auth.openai.com/device?state=opaque"
    assert view.user_code == "ABCD-EFGH"
    assert "private" not in view.model_dump_json()


def test_session_rejects_unapproved_url_and_untrusted_input_label() -> None:
    session = make_session()
    with pytest.raises(ValueError, match="hostname"):
        session.apply_update(
            ParsedAuthUpdate(verification_url="https://evil.example/login"),
            allowed_hosts=frozenset({"auth.openai.com"}),
        )
    with pytest.raises(ValidationError):
        session.apply_update(
            ParsedAuthUpdate(needs_input=True, input_label="raw CLI prompt"),
            allowed_hosts=frozenset({"auth.openai.com"}),
        )


def test_terminal_session_ignores_late_process_updates() -> None:
    session = make_session()
    session.mark_terminal(AuthSessionStatus.CANCELED)
    session.apply_update(
        ParsedAuthUpdate(authenticated=True),
        allowed_hosts=frozenset({"auth.openai.com"}),
    )
    assert session.view().status is AuthSessionStatus.CANCELED
