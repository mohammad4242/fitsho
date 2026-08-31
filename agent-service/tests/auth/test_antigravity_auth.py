from app.auth.adapters.antigravity import AntigravityAuthAdapter
from app.auth.schemas import AuthInputLabel, AuthSessionStatus


def test_antigravity_uses_hidden_remote_browser_auth_flow() -> None:
    adapter = AntigravityAuthAdapter(executable="agy")

    assert adapter.manual_auth_only is False
    assert adapter.command().executable == "agy"
    assert adapter.command().use_pty is True
    assert adapter.command().args == ()
    assert adapter.command().environment == (
        ("SSH_CONNECTION", "sandbox 0 sandbox 0"),
        ("SSH_CLIENT", "sandbox 0 0"),
    )
    assert adapter.allowed_auth_hosts() == frozenset({"accounts.google.com"})


def test_antigravity_parser_exposes_only_google_url_and_code_prompt() -> None:
    adapter = AntigravityAuthAdapter()
    handoff = adapter.parse_output(
        "\x1b[2KOpen https://accounts.google.com/o/oauth2/v2/auth?state=opaque\n"
        "Continue in your browser, then enter the authorization code:\n"
        "private token should never be returned"
    )

    assert handoff.verification_url == "https://accounts.google.com/o/oauth2/v2/auth?state=opaque"
    assert handoff.needs_input is True
    assert handoff.input_label == AuthInputLabel.AUTHORIZATION_CODE.value
    assert handoff.user_code is None
    assert "private" not in repr(handoff)


def test_antigravity_parser_fails_closed_for_unapproved_or_insecure_urls() -> None:
    adapter = AntigravityAuthAdapter()
    for text in (
        "Open https://evil.example/login",
        "Open http://accounts.google.com/login",
        "Open https://user:password@accounts.google.com/login",
    ):
        update = adapter.parse_output(text)
        assert update.failed is True
        assert update.verification_url is None
        assert update.user_code is None


def test_antigravity_exit_status_is_safe_and_deterministic() -> None:
    adapter = AntigravityAuthAdapter()
    assert adapter.classify_exit(0, "private output") is AuthSessionStatus.AUTHENTICATED
    assert adapter.classify_exit(143, "private stderr") is AuthSessionStatus.FAILED
