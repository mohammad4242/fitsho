from pathlib import Path

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


def test_codex_preserves_saved_credentials_across_interrupted_login(tmp_path: Path) -> None:
    adapter = CodexAuthAdapter()
    environment = {"HOME": str(tmp_path)}
    auth_path = tmp_path / ".codex" / "auth.json"
    auth_path.parent.mkdir(parents=True)
    auth_path.write_text('{"refresh_token":"keep"}\n', encoding="utf-8")

    marker = adapter.saved_credentials_marker(environment)
    assert marker is not None
    adapter.backup_saved_credentials(environment)
    auth_path.unlink()
    adapter.restore_saved_credentials(environment)

    assert auth_path.read_text(encoding="utf-8") == '{"refresh_token":"keep"}\n'
    assert adapter.saved_credentials_marker(environment) is not None
    adapter.finalize_saved_credentials(environment)
    assert not adapter.backup_path(environment).exists()


def test_codex_recovers_a_backup_left_by_container_restart(tmp_path: Path) -> None:
    adapter = CodexAuthAdapter()
    environment = {"HOME": str(tmp_path)}
    backup_path = adapter.backup_path(environment)
    backup_path.parent.mkdir(parents=True)
    backup_path.write_text('{"refresh_token":"recover"}\n', encoding="utf-8")

    adapter.recover_saved_credentials(environment)

    auth_path = tmp_path / ".codex" / "auth.json"
    assert auth_path.read_text(encoding="utf-8") == '{"refresh_token":"recover"}\n'
    assert not backup_path.exists()
