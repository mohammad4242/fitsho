import asyncio
import os
import sys
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import pytest

from app.auth.adapters.antigravity import AntigravityAuthAdapter
from app.auth.base import AuthCommand, ParsedAuthUpdate
from app.auth.manager import AuthManager, AuthManagerError
from app.auth.schemas import AuthSessionStatus
from app.schemas import AgentName, AuthState


def run[T](coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


class FakeAuthAdapter:
    agent = AgentName.CODEX
    manual_auth_only = False

    def __init__(self, script: Path) -> None:
        self.script = script

    def command(self) -> AuthCommand:
        return AuthCommand(sys.executable, (str(self.script),), use_pty=False)

    def allowed_auth_hosts(self) -> frozenset[str]:
        return frozenset({"auth.openai.com"})

    def parse_output(self, text: str) -> ParsedAuthUpdate:
        if "READY" in text:
            return ParsedAuthUpdate(
                verification_url="https://auth.openai.com/device?state=opaque",
                user_code="ABCD-EFGH",
            )
        if "INPUT" in text:
            return ParsedAuthUpdate(needs_input=True, input_label="authorization code")
        if "AUTHENTICATED" in text:
            return ParsedAuthUpdate(authenticated=True)
        return ParsedAuthUpdate()

    def classify_exit(self, returncode: int, final_text: str) -> AuthSessionStatus:
        del final_text
        return (
            AuthSessionStatus.AUTHENTICATED
            if returncode == 0
            else AuthSessionStatus.FAILED
        )


class FakePtyAuthAdapter:
    agent = AgentName.ANTIGRAVITY
    manual_auth_only = False

    def __init__(self, script: Path) -> None:
        self.script = script

    def command(self) -> AuthCommand:
        return AuthCommand(sys.executable, (str(self.script),), use_pty=True)

    def allowed_auth_hosts(self) -> frozenset[str]:
        return frozenset({"accounts.google.com"})

    def parse_output(self, text: str) -> ParsedAuthUpdate:
        if "AUTHENTICATED" in text:
            return ParsedAuthUpdate(authenticated=True)
        if "Open " in text or "READY" in text:
            return ParsedAuthUpdate(
                verification_url="https://accounts.google.com/o/oauth2/auth?state=opaque",
                needs_input=True,
                input_label="authorization code",
            )
        if "Select login method" in text:
            return ParsedAuthUpdate(press_enter=True)
        return ParsedAuthUpdate()

    def classify_exit(self, returncode: int, final_text: str) -> AuthSessionStatus:
        del final_text
        return AuthSessionStatus.AUTHENTICATED if returncode == 0 else AuthSessionStatus.FAILED


class ResettablePtyAuthAdapter(FakePtyAuthAdapter):
    def __init__(self, script: Path) -> None:
        super().__init__(script)
        self.reset_environments: list[dict[str, str]] = []

    def clear_saved_credentials(self, environment: dict[str, str]) -> None:
        self.reset_environments.append(environment)


class CredentialCompletingPtyAuthAdapter(FakePtyAuthAdapter):
    def __init__(self, script: Path) -> None:
        super().__init__(script)
        self.credentials_ready = False
        self.credential_generation = 0
        self.prompt_consumed = False

    def parse_output(self, text: str) -> ParsedAuthUpdate:
        if "AUTHENTICATED" in text:
            return ParsedAuthUpdate(authenticated=True)
        if not self.prompt_consumed and ("Open " in text or "READY" in text):
            self.prompt_consumed = True
            return ParsedAuthUpdate(
                verification_url="https://accounts.google.com/o/oauth2/auth?state=opaque",
                needs_input=True,
                input_label="authorization code",
            )
        return ParsedAuthUpdate()

    def has_saved_credentials(self, environment: dict[str, str]) -> bool:
        del environment
        return self.credentials_ready

    def saved_credentials_marker(self, environment: dict[str, str]) -> tuple[int, int, int] | None:
        del environment
        if not self.credentials_ready:
            return None
        return (1, self.credential_generation, 1)


def write_script(tmp_path: Path, body: str) -> Path:
    script = tmp_path / "fake-auth.py"
    script.write_text(body, encoding="utf-8")
    return script


def test_manager_starts_one_safe_session_and_rejects_duplicate(tmp_path: Path) -> None:
    script_body = "\n".join(
        [
            "import sys",
            "print('READY', flush=True)",
            "for line in sys.stdin:",
            "    if line.strip() == 'continue':",
            "        print('AUTHENTICATED', flush=True)",
            "        break",
        ]
    )
    script = write_script(
        tmp_path,
        script_body,
    )

    async def scenario() -> None:
        manager = AuthManager(
            {AgentName.CODEX: FakeAuthAdapter(script)},
            workspace=tmp_path,
            environment={"PATH": os.environ["PATH"], "AGENT_SERVICE_TOKEN": "private"},
        )
        view = await manager.start(AgentName.CODEX)
        assert view.status in {
            AuthSessionStatus.STARTING,
            AuthSessionStatus.WAITING_FOR_USER,
        }
        await asyncio.sleep(0.05)
        current = await manager.get(view.session_id)
        assert current.status is AuthSessionStatus.WAITING_FOR_USER
        assert current.verification_url is not None
        assert "private" not in current.model_dump_json()
        with pytest.raises(AuthManagerError, match="already in progress"):
            await manager.start(AgentName.CODEX)
        await manager.cancel(view.session_id)
        assert (await manager.get(view.session_id)).status is AuthSessionStatus.CANCELED
        await manager.shutdown()

    run(scenario())


def test_manager_exposes_pty_browser_handoff_and_completes_with_code(tmp_path: Path) -> None:
    script = write_script(
        tmp_path,
        "import sys\n"
        "print('READY', flush=True)\n"
        "if sys.stdin.readline().strip() == 'CODE':\n"
        "    print('AUTHENTICATED', flush=True)\n",
    )

    async def scenario() -> None:
        manager = AuthManager(
            {AgentName.ANTIGRAVITY: FakePtyAuthAdapter(script)},
            workspace=tmp_path,
            environment={"PATH": os.environ["PATH"]},
        )
        view = await manager.start(AgentName.ANTIGRAVITY)
        await asyncio.sleep(0.05)
        waiting = await manager.get(view.session_id)
        assert waiting.status is AuthSessionStatus.WAITING_FOR_INPUT
        assert waiting.verification_url == "https://accounts.google.com/o/oauth2/auth?state=opaque"
        assert waiting.input_label == "authorization code"
        verifying = await manager.submit_input(view.session_id, "CODE")
        assert verifying.status is AuthSessionStatus.VERIFYING
        await asyncio.sleep(0.05)
        assert (await manager.get(view.session_id)).status is AuthSessionStatus.AUTHENTICATED
        await manager.shutdown()

    run(scenario())


def test_manager_completes_when_saved_credentials_appear_after_code_submission(
    tmp_path: Path,
) -> None:
    script = write_script(
        tmp_path,
        "import time\n"
        "print('READY', flush=True)\n"
        "time.sleep(60)\n",
    )
    adapter = CredentialCompletingPtyAuthAdapter(script)

    async def scenario() -> None:
        manager = AuthManager(
            {AgentName.ANTIGRAVITY: adapter},
            workspace=tmp_path,
            environment={"PATH": os.environ["PATH"]},
        )
        try:
            view = await manager.start(AgentName.ANTIGRAVITY)
            await asyncio.sleep(0.05)
            waiting = await manager.get(view.session_id)
            assert waiting.status is AuthSessionStatus.WAITING_FOR_INPUT

            verifying = await manager.submit_input(view.session_id, "CODE")
            assert verifying.status is AuthSessionStatus.VERIFYING
            adapter.credentials_ready = True

            await asyncio.sleep(0.4)
            assert (await manager.get(view.session_id)).status is AuthSessionStatus.AUTHENTICATED
            process = manager._sessions[view.session_id].process  # noqa: SLF001
            assert process is not None
            assert not process.is_running
        finally:
            await manager.shutdown()

    run(scenario())


def test_manager_keeps_antigravity_verifying_after_pty_echoes_the_code(
    tmp_path: Path,
) -> None:
    script = write_script(
        tmp_path,
        "import sys, time\n"
        "print('Open https://accounts.google.com/o/oauth2/auth?state=opaque', flush=True)\n"
        "print('After authenticating, paste the authorization code below:', flush=True)\n"
        "sys.stdin.readline()\n"
        "time.sleep(60)\n",
    )
    adapter = AntigravityAuthAdapter(executable=sys.executable)
    adapter.command = lambda: AuthCommand(  # type: ignore[method-assign]
        sys.executable,
        (str(script),),
        use_pty=True,
    )

    async def scenario() -> None:
        manager = AuthManager(
            {AgentName.ANTIGRAVITY: adapter},
            workspace=tmp_path,
            environment={"HOME": str(tmp_path), "PATH": os.environ["PATH"]},
        )
        try:
            view = await manager.start(AgentName.ANTIGRAVITY)
            await asyncio.sleep(0.05)
            assert (
                await manager.get(view.session_id)
            ).status is AuthSessionStatus.WAITING_FOR_INPUT

            submitted = await manager.submit_input(view.session_id, "CODE")
            assert submitted.status is AuthSessionStatus.VERIFYING
            await asyncio.sleep(0.05)
            assert (
                await manager.get(view.session_id)
            ).status is AuthSessionStatus.VERIFYING
        finally:
            await manager.shutdown()

    run(scenario())


def test_manager_waits_for_a_new_saved_credential_marker(tmp_path: Path) -> None:
    script = write_script(
        tmp_path,
        "import time\n"
        "print('READY', flush=True)\n"
        "time.sleep(60)\n",
    )
    adapter = CredentialCompletingPtyAuthAdapter(script)
    adapter.credentials_ready = True
    adapter.credential_generation = 1

    async def scenario() -> None:
        manager = AuthManager(
            {AgentName.ANTIGRAVITY: adapter},
            workspace=tmp_path,
            environment={"PATH": os.environ["PATH"]},
        )
        try:
            view = await manager.start(AgentName.ANTIGRAVITY)
            await asyncio.sleep(0.05)
            assert (
                await manager.get(view.session_id)
            ).status is AuthSessionStatus.WAITING_FOR_INPUT

            verifying = await manager.submit_input(view.session_id, "CODE")
            assert verifying.status is AuthSessionStatus.VERIFYING
            await asyncio.sleep(0.35)
            assert (await manager.get(view.session_id)).status is AuthSessionStatus.VERIFYING

            adapter.credential_generation = 2
            await asyncio.sleep(0.35)
            assert (await manager.get(view.session_id)).status is AuthSessionStatus.AUTHENTICATED
        finally:
            await manager.shutdown()

    run(scenario())


def test_manager_force_reauth_clears_saved_credentials_before_start(tmp_path: Path) -> None:
    script = write_script(tmp_path, "import time\nprint('READY', flush=True)\ntime.sleep(60)\n")
    adapter = ResettablePtyAuthAdapter(script)

    async def scenario() -> None:
        manager = AuthManager(
            {AgentName.ANTIGRAVITY: adapter},
            workspace=tmp_path,
            environment={"HOME": str(tmp_path), "PATH": os.environ["PATH"]},
        )
        try:
            view = await manager.start(AgentName.ANTIGRAVITY, force_reauth=True)
            assert view.status in {
                AuthSessionStatus.STARTING,
                AuthSessionStatus.WAITING_FOR_USER,
            }
        finally:
            await manager.shutdown()

    run(scenario())
    assert adapter.reset_environments == [{"HOME": str(tmp_path), "PATH": os.environ["PATH"]}]


def test_manager_cancels_active_pty_auth_with_escape_and_releases_slot(tmp_path: Path) -> None:
    escaped_marker = tmp_path / "escaped.marker"
    script = write_script(
        tmp_path,
        "import os, sys, termios, time, tty\n"
        "print('READY', flush=True)\n"
        "fd=sys.stdin.fileno(); old=termios.tcgetattr(fd); tty.setraw(fd)\n"
        "value=os.read(fd, 1); termios.tcsetattr(fd, termios.TCSANOW, old)\n"
        f"open({str(escaped_marker)!r}, 'w', encoding='utf-8').write("
        "'yes' if value == bytes([27]) else 'no')\n"
        "time.sleep(60)\n",
    )

    async def scenario() -> None:
        manager = AuthManager(
            {AgentName.ANTIGRAVITY: FakePtyAuthAdapter(script)},
            workspace=tmp_path,
        )
        try:
            view = await manager.start(AgentName.ANTIGRAVITY)
            await asyncio.sleep(0.05)
            assert await manager.cancel_active(AgentName.ANTIGRAVITY) is True
            assert (await manager.get(view.session_id)).status is AuthSessionStatus.CANCELED
            process = manager._sessions[view.session_id].process  # noqa: SLF001
            assert process is not None
            assert not process.is_running
            assert escaped_marker.read_text(encoding='utf-8') == 'yes'
            assert await manager.cancel_active(AgentName.ANTIGRAVITY) is False
        finally:
            await manager.shutdown()

    run(scenario())


def test_manager_selects_antigravity_google_oauth_without_terminal_input(
    tmp_path: Path,
) -> None:
    script = write_script(
        tmp_path,
        "import sys\n"
        "print('Select login method:', flush=True)\n"
        "if sys.stdin.readline().strip() != '':\n"
        "    raise SystemExit(2)\n"
        "print('Open https://accounts.google.com/o/oauth2/auth?state=opaque', flush=True)\n"
        "print('After authenticating, paste the code below:', flush=True)\n"
        "if sys.stdin.readline().strip() == 'CODE':\n"
        "    print('AUTHENTICATED', flush=True)\n",
    )

    async def scenario() -> None:
        manager = AuthManager(
            {AgentName.ANTIGRAVITY: FakePtyAuthAdapter(script)},
            workspace=tmp_path,
        )
        view = await manager.start(AgentName.ANTIGRAVITY)
        await asyncio.sleep(0.1)
        waiting = await manager.get(view.session_id)
        assert waiting.status is AuthSessionStatus.WAITING_FOR_INPUT
        assert waiting.verification_url == "https://accounts.google.com/o/oauth2/auth?state=opaque"
        verifying = await manager.submit_input(view.session_id, "CODE")
        assert verifying.status is AuthSessionStatus.VERIFYING
        await asyncio.sleep(0.1)
        assert (await manager.get(view.session_id)).status is AuthSessionStatus.AUTHENTICATED
        await manager.shutdown()

    run(scenario())


def test_manager_submits_input_only_to_waiting_process_and_clears_it(tmp_path: Path) -> None:
    script = write_script(
        tmp_path,
        "import sys\nprint('READY', flush=True)\nline=sys.stdin.readline()\n"
        "print('AUTHENTICATED' if line.strip() == 'continue' else 'BAD', flush=True)\n",
    )

    async def scenario() -> None:
        manager = AuthManager(
            {AgentName.CODEX: FakeAuthAdapter(script)},
            workspace=tmp_path,
        )
        view = await manager.start(AgentName.CODEX)
        await asyncio.sleep(0.05)
        with pytest.raises(AuthManagerError) as error:
            await manager.submit_input(view.session_id, "unexpected")
        assert error.value.code == "auth_input_not_expected"
        session = manager._sessions[view.session_id]  # noqa: SLF001
        session.apply_update(
            ParsedAuthUpdate(needs_input=True, input_label="authorization code"),
            allowed_hosts=frozenset({"auth.openai.com"}),
        )
        awaiting = await manager.get(view.session_id)
        assert awaiting.status is AuthSessionStatus.WAITING_FOR_INPUT
        verifying = await manager.submit_input(view.session_id, "continue")
        assert verifying.status is AuthSessionStatus.VERIFYING
        await asyncio.sleep(0.05)
        assert (await manager.get(view.session_id)).status is AuthSessionStatus.AUTHENTICATED
        await manager.shutdown()

    run(scenario())


def test_manager_expires_and_terminates_pending_process(tmp_path: Path) -> None:
    script = write_script(tmp_path, "import time\ntime.sleep(60)\n")

    async def scenario() -> None:
        manager = AuthManager(
            {AgentName.CODEX: FakeAuthAdapter(script)},
            workspace=tmp_path,
            ttl_seconds=0.05,
        )
        view = await manager.start(AgentName.CODEX)
        await asyncio.sleep(0.15)
        assert (await manager.get(view.session_id)).status is AuthSessionStatus.EXPIRED
        process = manager._sessions[view.session_id].process  # noqa: SLF001
        assert process is not None
        assert not process.is_running
        await manager.shutdown()

    run(scenario())


def test_manager_reports_success_and_releases_active_session(tmp_path: Path) -> None:
    script = write_script(tmp_path, "print('AUTHENTICATED', flush=True)\n")
    states: list[tuple[AgentName, AuthState]] = []

    async def scenario() -> None:
        manager = AuthManager(
            {AgentName.CODEX: FakeAuthAdapter(script)},
            workspace=tmp_path,
            state_callback=lambda agent, state: states.append((agent, state)),
        )
        view = await manager.start(AgentName.CODEX)
        await asyncio.sleep(0.1)
        assert (await manager.get(view.session_id)).status is AuthSessionStatus.AUTHENTICATED
        next_view = await manager.start(AgentName.CODEX)
        assert next_view.status in {
            AuthSessionStatus.STARTING,
            AuthSessionStatus.AUTHENTICATED,
        }
        await manager.shutdown()

    run(scenario())
    assert states == [(AgentName.CODEX, AuthState.AUTHENTICATED)]


def test_manager_rejects_input_after_cancel_and_shutdown_reaps_process(
    tmp_path: Path,
) -> None:
    script = write_script(tmp_path, "import time\ntime.sleep(60)\n")

    async def scenario() -> None:
        manager = AuthManager(
            {AgentName.CODEX: FakeAuthAdapter(script)},
            workspace=tmp_path,
        )
        view = await manager.start(AgentName.CODEX)
        await asyncio.sleep(0.05)
        process = manager._sessions[view.session_id].process  # noqa: SLF001
        assert process is not None
        await manager.cancel(view.session_id)
        with pytest.raises(AuthManagerError) as error:
            await manager.submit_input(view.session_id, "token")
        assert error.value.code == "auth_input_not_expected"

        second = await manager.start(AgentName.CODEX)
        await asyncio.sleep(0.05)
        second_process = manager._sessions[second.session_id].process  # noqa: SLF001
        assert second_process is not None
        await manager.shutdown()
        assert not process.is_running
        assert not second_process.is_running
        assert manager._sessions == {}  # noqa: SLF001

    run(scenario())
