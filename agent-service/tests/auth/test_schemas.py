from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.auth.schemas import (
    AuthInputRequest,
    AuthSessionStatus,
    AuthSessionView,
    AuthStartRequest,
)
from app.schemas import AgentName


def _view(**overrides: object) -> AuthSessionView:
    values: dict[str, object] = {
        "session_id": uuid4(),
        "agent": AgentName.CODEX,
        "status": AuthSessionStatus.WAITING_FOR_USER,
        "expires_at": datetime.now(UTC) + timedelta(minutes=5),
    }
    values.update(overrides)
    return AuthSessionView.model_validate(values)


def test_auth_start_accepts_only_known_agent_and_forbids_extra_fields() -> None:
    assert AuthStartRequest(agent=AgentName.CLAUDE).agent is AgentName.CLAUDE
    with pytest.raises(ValidationError):
        AuthStartRequest.model_validate({"agent": "codex", "command": "codex login"})


def test_auth_input_has_bounded_non_empty_value_and_forbids_extra_fields() -> None:
    assert AuthInputRequest(value="safe-value").value == "safe-value"
    with pytest.raises(ValidationError):
        AuthInputRequest(value="\n")
    with pytest.raises(ValidationError):
        AuthInputRequest(value="x" * 4097)
    with pytest.raises(ValidationError):
        AuthInputRequest.model_validate({"value": "safe", "agent": "codex"})


def test_auth_view_accepts_safe_public_fields_only() -> None:
    view = _view(
        verification_url="https://auth.openai.com/oauth/authorize?state=opaque",
        user_code="ABCD-EFGH",
        input_label="authorization code",
        safe_error_message="authentication failed",
    )
    assert view.verification_url == "https://auth.openai.com/oauth/authorize?state=opaque"
    assert view.user_code == "ABCD-EFGH"


@pytest.mark.parametrize(
    "url",
    [
        "http://auth.openai.com/login",
        "https://user:password@auth.openai.com/login",
        "https://auth.openai.com/login\nX-Leak: secret",
        "not-a-url",
    ],
)
def test_auth_view_rejects_unsafe_verification_url_shape(url: str) -> None:
    with pytest.raises(ValidationError):
        _view(verification_url=url)


@pytest.mark.parametrize("code", ["", "AB\nCD", "\x1b[31msecret", "x" * 257])
def test_auth_view_rejects_control_or_unbounded_user_code(code: str) -> None:
    with pytest.raises(ValidationError):
        _view(user_code=code)


def test_auth_view_rejects_untrusted_prompt_and_error_text() -> None:
    with pytest.raises(ValidationError):
        _view(input_label="raw CLI prompt: paste token here")
    with pytest.raises(ValidationError):
        _view(safe_error_message="provider stderr contains a private token")


def test_auth_view_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        _view(token="secret")
