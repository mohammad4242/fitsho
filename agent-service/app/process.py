import asyncio
import os
import signal
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


class ProcessTimeoutError(TimeoutError):
    """Raised when a process does not finish within its permitted time."""


class ProcessExecutionError(RuntimeError):
    """Raised when a process cannot be started."""


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str


async def run_process(
    command: Sequence[str],
    *,
    workspace: Path,
    timeout_seconds: float,
    input_text: str | None = None,
    env: Mapping[str, str] | None = None,
    inherit_environment: bool = True,
) -> ProcessResult:
    if not command:
        raise ValueError("command must not be empty")
    if timeout_seconds <= 0:
        raise ValueError("timeout must be positive")

    process_environment: dict[str, str] | None
    if env is None:
        process_environment = None if inherit_environment else {}
    else:
        process_environment = {**os.environ, **env} if inherit_environment else dict(env)
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workspace,
            start_new_session=True,
            env=process_environment,
        )
    except (OSError, ValueError):
        raise ProcessExecutionError("process could not be started") from None

    communication = asyncio.create_task(
        process.communicate(None if input_text is None else input_text.encode())
    )
    try:
        stdout, stderr = await asyncio.wait_for(asyncio.shield(communication), timeout_seconds)
    except TimeoutError as exc:
        await _stop_process_group(process)
        await _reap_communication(communication)
        raise ProcessTimeoutError("process timed out") from exc
    except BaseException:
        await _stop_process_group(process)
        await _reap_communication(communication)
        raise

    return ProcessResult(
        returncode=process.returncode if process.returncode is not None else -1,
        stdout=stdout.decode(errors="replace"),
        stderr=stderr.decode(errors="replace"),
    )


async def _stop_process_group(process: asyncio.subprocess.Process) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass

    if process.returncode is None:
        try:
            await asyncio.wait_for(asyncio.shield(process.wait()), timeout=0.3)
        except TimeoutError:
            pass
    else:
        await asyncio.sleep(0.05)

    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    await process.wait()


async def _reap_communication(communication: asyncio.Task[tuple[bytes, bytes]]) -> None:
    try:
        await asyncio.wait_for(asyncio.shield(communication), timeout=0.5)
    except TimeoutError:
        communication.cancel()
        await asyncio.gather(communication, return_exceptions=True)
