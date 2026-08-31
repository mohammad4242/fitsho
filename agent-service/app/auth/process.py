from __future__ import annotations

import asyncio
import os
import signal
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from .base import AuthCommand

AuthOutputCallback = Callable[[str], Awaitable[None]]

_SAFE_EXACT_KEYS = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "LANG",
        "LC_ALL",
        "TERM",
        "TMPDIR",
        "DBUS_SESSION_BUS_ADDRESS",
        "DISPLAY",
        "NO_PROXY",
        "no_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "http_proxy",
        "https_proxy",
        "ALL_PROXY",
        "all_proxy",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "CLAUDE_CODE_DISABLE_AUTOUPDATE",
    }
)


class AuthProcessError(RuntimeError):
    """Raised when an interactive authentication process cannot be managed."""


@dataclass(frozen=True)
class AuthProcessResult:
    returncode: int
    final_text: str
    output_truncated: bool


def safe_auth_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    """Copy only runtime values that are safe and necessary for provider login."""

    environment = os.environ if source is None else source
    return {
        key: value
        for key, value in environment.items()
        if key in _SAFE_EXACT_KEYS or key.startswith("XDG_")
    }


class AuthProcess:
    def __init__(
        self,
        command: AuthCommand,
        *,
        workspace: Path,
        environment: Mapping[str, str],
        max_output_bytes: int,
        output_callback: AuthOutputCallback,
    ) -> None:
        if not command.executable.strip():
            raise ValueError("auth executable must not be empty")
        if max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be positive")
        if command.use_pty:
            raise AuthProcessError("PTY authentication is not supported by this adapter")
        self.command = command
        self.workspace = workspace
        self.environment = dict(environment)
        self.max_output_bytes = max_output_bytes
        self.output_callback = output_callback
        self._process: asyncio.subprocess.Process | None = None
        self._monitor_task: asyncio.Task[AuthProcessResult] | None = None
        self._stdout = bytearray()
        self._stderr = bytearray()
        self._output_size = 0
        self._output_truncated = False

    @property
    def is_running(self) -> bool:
        process = self._process
        return process is not None and process.returncode is None

    async def start(self) -> None:
        if self._process is not None:
            raise AuthProcessError("authentication process already started")
        try:
            self.workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
            self._process = await asyncio.create_subprocess_exec(
                self.command.executable,
                *self.command.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.workspace,
                env=self.environment,
                start_new_session=True,
            )
        except (OSError, ValueError) as exc:
            raise AuthProcessError("authentication process could not be started") from exc
        self._monitor_task = asyncio.create_task(self._monitor())

    async def send_input(self, value: str) -> None:
        if not value.isprintable() or not value.strip():
            raise AuthProcessError("authentication input is invalid")
        process = self._process
        if process is None or process.returncode is not None or process.stdin is None:
            raise AuthProcessError("authentication process is not running")
        try:
            process.stdin.write(value.encode("utf-8") + b"\n")
            await process.stdin.drain()
        except (BrokenPipeError, ConnectionError, OSError) as exc:
            raise AuthProcessError("authentication process is not accepting input") from exc

    async def wait(self) -> AuthProcessResult:
        task = self._monitor_task
        if task is None:
            raise AuthProcessError("authentication process has not started")
        return await asyncio.shield(task)

    async def terminate(self) -> None:
        task = self._monitor_task
        await self._stop_process()
        if task is not None and task is not asyncio.current_task():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                pass

    async def _monitor(self) -> AuthProcessResult:
        process = self._process
        if process is None or process.stdout is None or process.stderr is None:
            raise AuthProcessError("authentication process is not ready")
        stdout_reader = asyncio.create_task(self._read_stream(process.stdout, self._stdout))
        stderr_reader = asyncio.create_task(self._read_stream(process.stderr, self._stderr))
        try:
            returncode = await process.wait()
            await asyncio.gather(stdout_reader, stderr_reader, return_exceptions=True)
            final_text = bytes(self._stdout + self._stderr).decode("utf-8", errors="replace")
            return AuthProcessResult(returncode, final_text, self._output_truncated)
        except asyncio.CancelledError:
            await self._stop_process()
            await asyncio.gather(stdout_reader, stderr_reader, return_exceptions=True)
            raise
        finally:
            self._stdout.clear()
            self._stderr.clear()

    async def _read_stream(self, stream: asyncio.StreamReader, buffer: bytearray) -> None:
        while True:
            chunk = await stream.read(4096)
            if not chunk:
                return
            remaining = self.max_output_bytes - self._output_size
            accepted = chunk[: max(0, remaining)]
            if len(accepted) < len(chunk):
                self._output_truncated = True
            if not accepted:
                continue
            buffer.extend(accepted)
            self._output_size += len(accepted)
            await self.output_callback(accepted.decode("utf-8", errors="replace"))

    async def _stop_process(self) -> None:
        process = self._process
        if process is None:
            return
        if process.stdin is not None:
            process.stdin.close()
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(asyncio.shield(process.wait()), timeout=0.5)
            except TimeoutError:
                pass
        if process.returncode is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()
