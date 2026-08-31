from pathlib import Path

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


def test_antigravity_clears_only_its_saved_oauth_token_for_reauthentication(
    tmp_path: Path,
) -> None:
    token_path = tmp_path / ".gemini" / "antigravity-cli" / "antigravity-oauth-token"
    token_path.parent.mkdir(parents=True)
    token_path.write_text("credential", encoding="utf-8")
    unrelated = tmp_path / "unrelated.txt"
    unrelated.write_text("keep", encoding="utf-8")

    AntigravityAuthAdapter().clear_saved_credentials({"HOME": str(tmp_path)})

    assert not token_path.exists()
    assert unrelated.read_text(encoding="utf-8") == "keep"


def test_antigravity_reports_non_empty_saved_oauth_credentials(tmp_path: Path) -> None:
    adapter = AntigravityAuthAdapter()

    assert adapter.has_saved_credentials({"HOME": str(tmp_path)}) is False

    token_path = tmp_path / ".gemini" / "antigravity-cli" / "antigravity-oauth-token"
    token_path.parent.mkdir(parents=True)
    token_path.write_text("credential", encoding="utf-8")
    assert adapter.has_saved_credentials({"HOME": str(tmp_path)}) is True
    marker = adapter.saved_credentials_marker({"HOME": str(tmp_path)})
    assert marker is not None

    token_path.write_text("updated-credential", encoding="utf-8")
    assert adapter.saved_credentials_marker({"HOME": str(tmp_path)}) != marker

    token_path.write_text("", encoding="utf-8")
    assert adapter.has_saved_credentials({"HOME": str(tmp_path)}) is False


def test_antigravity_parser_exposes_only_google_url_and_code_prompt() -> None:
    adapter = AntigravityAuthAdapter()
    handoff = adapter.parse_output(
        "\x1b[2KOpen https://accounts.google.com/o/oauth2/v2/auth?state=opaque\n"
        "After authenticating, copy the code displayed in the browser and paste it below:\n"
        "authorization code...\n"
        "private token should never be returned"
    )

    assert handoff.verification_url == "https://accounts.google.com/o/oauth2/v2/auth?state=opaque"
    assert handoff.needs_input is True
    assert handoff.input_label == AuthInputLabel.AUTHORIZATION_CODE.value
    assert handoff.user_code is None
    assert "private" not in repr(handoff)


def test_antigravity_parser_strips_terminal_hyperlink_controls_from_url() -> None:
    adapter = AntigravityAuthAdapter()
    handoff = adapter.parse_output(
        "\x1b]8;id=opaque;https://accounts.google.com/o/oauth2/auth?state=opaque "
        "Click here\x1b]8;;\x07"
    )

    assert handoff.verification_url is not None
    assert all(ord(char) >= 0x20 for char in handoff.verification_url)


def test_antigravity_parser_ignores_terminal_bells_around_redrawn_urls() -> None:
    adapter = AntigravityAuthAdapter()
    handoff = adapter.parse_output(
        "\x07https://accounts.google.com/o/oauth2/auth?state=opaque\x07"
    )

    assert handoff.verification_url == "https://accounts.google.com/o/oauth2/auth?state=opaque"


def test_antigravity_parser_requests_only_fixed_google_oauth_menu_selection() -> None:
    adapter = AntigravityAuthAdapter()

    handoff = adapter.parse_output(
        "Select login method:\n> 1. Google OAuth\n2. Use a Google Cloud project"
    )

    assert handoff.press_enter is True
    assert handoff.verification_url is None


def test_antigravity_parser_reports_rejected_authorization_code() -> None:
    adapter = AntigravityAuthAdapter()

    handoff = adapter.parse_output(
        "After authenticating, copy the code displayed in the browser and paste it below:\n"
        "authorization code...\n"
        "Got an error: token exchange failed: oauth2: invalid_grant Malformed auth code."
    )

    assert handoff.failed is True
    assert handoff.needs_input is False
    assert handoff.safe_error_message == "authentication failed"


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
