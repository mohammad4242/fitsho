from app.auth.adapters.codex import CodexAuthAdapter
from app.auth.schemas import AuthSessionStatus


def test_codex_uses_the_pinned_device_auth_command_without_a_pty() -> None:
    command = CodexAuthAdapter(executable="codex").command()

    assert command.executable == "codex"
    assert command.args == ("login", "--device-auth")
    assert command.use_pty is False


def test_codex_parser_strips_ansi_and_exposes_only_safe_handoff_fields() -> None:
    adapter = CodexAuthAdapter()
    update = adapter.parse_output(
        "\x1b[2KOpen https://auth.openai.com/codex/device?state=opaque\n"
        "Device code: ABCD-EFGH\x1b[0m\n"
        "private token should never be returned"
    )

    assert update.verification_url == "https://auth.openai.com/codex/device?state=opaque"
    assert update.user_code == "ABCD-EFGH"
    assert update.failed is False
    assert "private" not in repr(update)


def test_codex_parser_extracts_one_time_code_printed_after_prompt() -> None:
    adapter = CodexAuthAdapter()
    update = adapter.parse_output(
        "1. Open https://auth.openai.com/codex/device?state=opaque\n"
        "2. Enter this one-time code (expires in 15 minutes)\n"
        "   \x1b[90mABCD-EFGHI\x1b[0m\n"
        "Continue only if you started this login in Codex."
    )

    assert update.verification_url == "https://auth.openai.com/codex/device?state=opaque"
    assert update.user_code == "ABCD-EFGHI"
    assert update.needs_input is False
    assert update.input_label is None
    assert update.failed is False


def test_codex_parser_fails_closed_for_unapproved_or_insecure_urls() -> None:
    adapter = CodexAuthAdapter()
    for text in (
        "Open https://evil.example/login",
        "Open http://auth.openai.com/login",
        "Open https://user:password@auth.openai.com/login",
    ):
        update = adapter.parse_output(text)
        assert update.failed is True
        assert update.verification_url is None
        assert update.user_code is None


def test_codex_exit_status_is_safe_and_deterministic() -> None:
    adapter = CodexAuthAdapter()
    assert adapter.classify_exit(0, "private token") is AuthSessionStatus.AUTHENTICATED
    assert adapter.classify_exit(143, "private stderr") is AuthSessionStatus.FAILED
