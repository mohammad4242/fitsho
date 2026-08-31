from __future__ import annotations

import asyncio
import errno
import fcntl
import os
import pty
import signal
import struct
import termios
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
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_CACHE_HOME",
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
        if key in _SAFE_EXACT_KEYS
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
        self.command = command
        self.workspace = workspace
        self.environment = dict(environment)
        self.max_output_bytes = max_output_bytes
        self.output_callback = output_callback
        self._process: asyncio.subprocess.Process | None = None
        self._monitor_task: asyncio.Task[AuthProcessResult] | None = None
        self._pty_master_fd: int | None = None
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
        slave_fd: int | None = None
        try:
            self.workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
            if self.command.use_pty:
                master_fd, slave_fd = pty.openpty()
                self._configure_pty(master_fd)
                self._pty_master_fd = master_fd
                process_environment = {
                    **self.environment,
                    **dict(self.command.environment),
                }
                process_environment.setdefault("SSH_TTY", os.ttyname(slave_fd))
                self._process = await asyncio.create_subprocess_exec(
                    self.command.executable,
                    *self.command.args,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    cwd=self.workspace,
                    env=process_environment,
                    start_new_session=True,
                )
            else:
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
            self._close_pty_master()
            raise AuthProcessError("authentication process could not be started") from exc
        finally:
            if slave_fd is not None:
                try:
                    os.close(slave_fd)
                except OSError:
                    pass
        self._monitor_task = asyncio.create_task(self._monitor())

    async def send_input(self, value: str) -> None:
        if not value.isprintable() or not value.strip():
            raise AuthProcessError("authentication input is invalid")
        process = self._process
        if self.command.use_pty:
            master_fd = self._pty_master_fd
            if process is None or process.returncode is not None or master_fd is None:
                raise AuthProcessError("authentication process is not running")
            try:
                await self._write_pty(master_fd, value.encode("utf-8") + b"\n")
            except (BrokenPipeError, ConnectionError, OSError) as exc:
                raise AuthProcessError("authentication process is not accepting input") from exc
            return
        if process is None or process.returncode is not None or process.stdin is None:
            raise AuthProcessError("authentication process is not running")
        try:
            process.stdin.write(value.encode("utf-8") + b"\n")
            await process.stdin.drain()
        except (BrokenPipeError, ConnectionError, OSError) as exc:
            raise AuthProcessError("authentication process is not accepting input") from exc

    async def press_enter(self) -> None:
        """Send the fixed Enter action requested by an adapter's safe prompt parser."""

        process = self._process
        master_fd = self._pty_master_fd
        if (
            not self.command.use_pty
            or process is None
            or process.returncode is not None
            or master_fd is None
        ):
            raise AuthProcessError("authentication process is not running")
        try:
            await self._write_pty(master_fd, b"\r")
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
                await asyncio.wait_for(asyncio.shield(task), timeout=1.0)
            except TimeoutError:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            except asyncio.CancelledError:
                pass

    async def _monitor(self) -> AuthProcessResult:
        process = self._process
        if self.command.use_pty:
            return await self._monitor_pty()
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

    async def _monitor_pty(self) -> AuthProcessResult:
        process = self._process
        master_fd = self._pty_master_fd
        if process is None or master_fd is None:
            raise AuthProcessError("authentication process is not ready")
        reader_task = asyncio.create_task(self._drain_pty(master_fd))
        try:
            returncode = await process.wait()
            await reader_task
            final_text = bytes(self._stdout).decode("utf-8", errors="replace")
            return AuthProcessResult(returncode, final_text, self._output_truncated)
        except asyncio.CancelledError:
            reader_task.cancel()
            await asyncio.gather(reader_task, return_exceptions=True)
            await self._stop_process()
            raise
        finally:
            self._close_pty_master()

    async def _drain_pty(self, master_fd: int) -> None:
        while True:
            chunk = await self._read_pty_chunk(master_fd)
            if not chunk:
                return
            remaining = self.max_output_bytes - self._output_size
            accepted = chunk[: max(0, remaining)]
            if len(accepted) < len(chunk):
                self._output_truncated = True
            if not accepted:
                continue
            self._stdout.extend(accepted)
            self._output_size += len(accepted)
            await self.output_callback(accepted.decode("utf-8", errors="replace"))

    @staticmethod
    def _configure_pty(master_fd: int) -> None:
        os.set_blocking(master_fd, False)
        fcntl.ioctl(master_fd, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 120, 0, 0))

    async def _read_pty_chunk(self, master_fd: int) -> bytes:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bytes] = loop.create_future()

        def on_readable() -> None:
            try:
                chunk = os.read(master_fd, 4096)
            except BlockingIOError:
                return
            except OSError as exc:
                if exc.errno == errno.EIO:
                    chunk = b""
                elif not future.done():
                    future.set_exception(exc)
                else:
                    return
            if not future.done():
                future.set_result(chunk)

        loop.add_reader(master_fd, on_readable)
        try:
            return await future
        finally:
            loop.remove_reader(master_fd)

    async def _write_pty(self, master_fd: int, data: bytes) -> None:
        loop = asyncio.get_running_loop()
        offset = 0
        while offset < len(data):
            try:
                offset += os.write(master_fd, data[offset:])
                continue
            except BlockingIOError:
                writable: asyncio.Future[None] = loop.create_future()

                def on_writable(future: asyncio.Future[None] = writable) -> None:
                    if not future.done():
                        future.set_result(None)

                loop.add_writer(master_fd, on_writable)
                try:
                    await writable
                finally:
                    loop.remove_writer(master_fd)

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
        self._close_pty_master()

    def _close_pty_master(self) -> None:
        master_fd = self._pty_master_fd
        self._pty_master_fd = None
        if master_fd is None:
            return
        try:
            os.close(master_fd)
        except OSError:
            pass
