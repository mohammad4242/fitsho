import asyncio
import json
import os
import sys
import time
from collections.abc import Coroutine, Sequence
from pathlib import Path
from typing import Any

import pytest

from app.auth.base import AuthCommand
from app.auth.process import AuthProcess, safe_auth_environment
from app.process import ProcessTimeoutError, run_process


def run[T](coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


def test_prompt_text_stays_data_and_process_uses_requested_cwd(tmp_path: Path) -> None:
    injected = "hello; touch SHOULD_NOT_EXIST && echo injected"
    script = "import json, os, sys; print(json.dumps({'args': sys.argv[1:], 'cwd': os.getcwd()}))"

    result = run(
        run_process(
            [sys.executable, "-c", script, injected],
            workspace=tmp_path,
            timeout_seconds=2,
            input_text=injected,
        )
    )

    payload = json.loads(result.stdout)
    assert payload["args"] == [injected]
    assert payload["cwd"] == str(tmp_path)
    assert not (tmp_path / "SHOULD_NOT_EXIST").exists()


def test_nonzero_process_returns_captured_output_without_raising(tmp_path: Path) -> None:
    result = run(
        run_process(
            [
                sys.executable,
                "-c",
                "print('out'); print('err', file=__import__('sys').stderr); raise SystemExit(7)",
            ],
            workspace=tmp_path,
            timeout_seconds=2,
        )
    )

    assert result.returncode == 7
    assert result.stdout == "out\n"
    assert result.stderr == "err\n"


def test_process_can_run_with_an_explicit_non_inherited_environment(tmp_path: Path) -> None:
    script = "import os; print(os.environ.get('AGENT_SERVICE_TOKEN', 'missing'))"
    result = run(
        run_process(
            [sys.executable, "-c", script],
            workspace=tmp_path,
            timeout_seconds=2,
            env={"PATH": os.environ["PATH"], "AGENT_CHILD_MARKER": "ok"},
            inherit_environment=False,
        )
    )

    assert result.stdout.strip() == "missing"


def test_timeout_terminates_process_group_and_does_not_leave_child_running(tmp_path: Path) -> None:
    pid_file = tmp_path / "child.pid"
    script = (
        "import pathlib, subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        f"pathlib.Path({str(pid_file)!r}).write_text(str(child.pid)); "
        "time.sleep(60)"
    )

    with pytest.raises(ProcessTimeoutError, match="timed out"):
        run(run_process([sys.executable, "-c", script], workspace=tmp_path, timeout_seconds=0.1))

    child_pid = int(pid_file.read_text())
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and _pid_is_running(child_pid):
        time.sleep(0.02)
    assert not _pid_is_running(child_pid)


def test_timeout_escalates_when_process_ignores_sigterm(tmp_path: Path) -> None:
    script = "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)"
    with pytest.raises(ProcessTimeoutError):
        run(run_process([sys.executable, "-c", script], workspace=tmp_path, timeout_seconds=0.1))


def test_cancellation_stops_the_process_and_reaps_it(tmp_path: Path) -> None:
    async def scenario() -> None:
        task = asyncio.create_task(
            run_process(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                workspace=tmp_path,
                timeout_seconds=60,
            )
        )
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(scenario())


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@pytest.mark.parametrize("command", [[], ()])
def test_empty_command_is_rejected(tmp_path: Path, command: Sequence[str]) -> None:
    with pytest.raises(ValueError, match="command"):
        run(run_process(command, workspace=tmp_path, timeout_seconds=1))


def test_nonpositive_timeout_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="timeout"):
        run(run_process([sys.executable, "-c", ""], workspace=tmp_path, timeout_seconds=0))


def test_auth_environment_is_an_exact_allowlist() -> None:
    environment = safe_auth_environment(
        {
            "PATH": "/usr/bin",
            "HOME": "/home/agent",
            "XDG_CONFIG_HOME": "/home/agent/.config",
            "XDG_SECRET": "private-token",
            "AGENT_SERVICE_TOKEN": "service-token",
            "OPENAI_API_KEY": "provider-token",
        }
    )

    assert environment == {
        "PATH": "/usr/bin",
        "HOME": "/home/agent",
        "XDG_CONFIG_HOME": "/home/agent/.config",
    }


def test_auth_process_uses_exec_not_shell_and_bounds_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exec_calls: list[tuple[object, ...]] = []
    original_exec = asyncio.create_subprocess_exec

    async def recording_exec(*args: object, **kwargs: object) -> asyncio.subprocess.Process:
        exec_calls.append(args)
        return await original_exec(*args, **kwargs)  # type: ignore[arg-type]

    async def forbidden_shell(*args: object, **kwargs: object) -> Any:
        raise AssertionError(f"shell invocation: {args}, {kwargs}")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", recording_exec)
    monkeypatch.setattr(asyncio, "create_subprocess_shell", forbidden_shell)
    output: list[str] = []

    async def collect_output(text: str) -> None:
        output.append(text)

    async def scenario() -> None:
        process = AuthProcess(
            AuthCommand(sys.executable, ("-c", "print('x' * 1000)"), use_pty=False),
            workspace=tmp_path,
            environment={"PATH": os.environ["PATH"]},
            max_output_bytes=32,
            output_callback=collect_output,
        )
        await process.start()
        result = await process.wait()
        assert result.returncode == 0
        assert result.output_truncated is True
        assert len(result.final_text.encode()) <= 32

    run(scenario())
    assert exec_calls


def test_auth_process_supports_pty_output_and_termination(
    tmp_path: Path,
) -> None:
    output: list[str] = []

    async def collect(text: str) -> None:
        output.append(text)

    async def scenario() -> None:
        process = AuthProcess(
            AuthCommand(
                sys.executable,
                (
                    "-c",
                    "import os, time; "
                    "print(f'WIDTH={os.get_terminal_size().columns}', flush=True); "
                    "time.sleep(60)",
                ),
                use_pty=True,
            ),
            workspace=tmp_path,
            environment={"PATH": os.environ["PATH"]},
            max_output_bytes=4096,
            output_callback=collect,
        )
        await process.start()
        await asyncio.sleep(0.05)
        assert process.is_running
        assert "WIDTH=4096" in "".join(output)
        await process.terminate()
        assert not process.is_running

    run(scenario())


def test_auth_process_merges_only_fixed_command_environment_for_pty(
    tmp_path: Path,
) -> None:
    output: list[str] = []

    async def collect(text: str) -> None:
        output.append(text)

    async def scenario() -> None:
        process = AuthProcess(
            AuthCommand(
                sys.executable,
                (
                    "-c",
                    "import os; print(os.environ.get('SSH_CONNECTION')); "
                    "print(os.environ.get('SSH_TTY', '').startswith('/dev/pts/'))",
                ),
                use_pty=True,
                environment=(("SSH_CONNECTION", "sandbox 0 sandbox 0"),),
            ),
            workspace=tmp_path,
            environment={"PATH": os.environ["PATH"], "AGENT_SERVICE_TOKEN": "secret"},
            max_output_bytes=4096,
            output_callback=collect,
        )
        await process.start()
        result = await process.wait()
        assert result.returncode == 0

    run(scenario())
    assert "sandbox 0 sandbox 0" in "".join(output)
    assert "True" in "".join(output)
    assert "secret" not in "".join(output)


def test_auth_process_can_press_fixed_enter_in_pty_mode(tmp_path: Path) -> None:
    output: list[str] = []

    async def collect(text: str) -> None:
        output.append(text)

    async def scenario() -> None:
        process = AuthProcess(
            AuthCommand(
                sys.executable,
                (
                    "-c",
                    "import sys; print('MENU', flush=True); "
                    "sys.stdin.readline(); print('DONE', flush=True)",
                ),
                use_pty=True,
            ),
            workspace=tmp_path,
            environment={"PATH": os.environ["PATH"]},
            max_output_bytes=4096,
            output_callback=collect,
        )
        await process.start()
        await asyncio.sleep(0.05)
        await process.press_enter()
        result = await process.wait()
        assert result.returncode == 0

    run(scenario())
    assert "DONE" in "".join(output)


def test_auth_process_can_press_fixed_escape_in_pty_mode(tmp_path: Path) -> None:
    output: list[str] = []

    async def collect(text: str) -> None:
        output.append(text)

    async def scenario() -> None:
        process = AuthProcess(
            AuthCommand(
                sys.executable,
                (
                    "-c",
                    "import os, sys, termios, tty; "
                    "fd=sys.stdin.fileno(); old=termios.tcgetattr(fd); tty.setraw(fd); "
                    "value=os.read(fd, 1); termios.tcsetattr(fd, termios.TCSANOW, old); "
                    "print('ESCAPED' if value == bytes([27]) else 'WRONG', flush=True)",
                ),
                use_pty=True,
            ),
            workspace=tmp_path,
            environment={"PATH": os.environ["PATH"]},
            max_output_bytes=4096,
            output_callback=collect,
        )
        await process.start()
        try:
            await asyncio.sleep(0.05)
            await process.press_escape()
            result = await process.wait()
            assert result.returncode == 0
        finally:
            if process.is_running:
                await process.terminate()

    run(scenario())
    assert "ESCAPED" in "".join(output)
