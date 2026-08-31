from app.auth.adapters.claude import ClaudeAuthAdapter
from app.auth.schemas import AuthSessionStatus


def test_claude_uses_the_pinned_subscription_login_command_without_a_pty() -> None:
    command = ClaudeAuthAdapter(executable="claude").command()

    assert command.executable == "claude"
    assert command.args == ("auth", "login")
    assert command.use_pty is False


def test_claude_parser_returns_only_allowlisted_https_handoff() -> None:
    adapter = ClaudeAuthAdapter()
    update = adapter.parse_output(
        "Sign in at https://claude.com/oauth/authorize?state=opaque\n"
        "private authorization token"
    )

    assert update.verification_url == "https://claude.com/oauth/authorize?state=opaque"
    assert update.user_code is None
    assert "private" not in repr(update)


def test_claude_parser_fails_closed_for_unapproved_url() -> None:
    update = ClaudeAuthAdapter().parse_output("https://evil.example/login")

    assert update.failed is True
    assert update.verification_url is None


def test_claude_exit_status_is_safe_and_deterministic() -> None:
    adapter = ClaudeAuthAdapter()
    assert adapter.classify_exit(0, "private output") is AuthSessionStatus.AUTHENTICATED
    assert adapter.classify_exit(1, "private stderr") is AuthSessionStatus.FAILED
