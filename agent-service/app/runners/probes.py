from __future__ import annotations

import asyncio
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from ..process import ProcessExecutionError, ProcessResult, ProcessTimeoutError, run_process
from ..schemas import AuthState

AuthStatusParser = Callable[[ProcessResult], AuthState]
EnvironmentProvider = Mapping[str, str] | Callable[[], Mapping[str, str]]

_ANSI_ESCAPE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._()/-]{0,127}$")


@dataclass
class CliMetadataProbe:
    executable: str
    workspace: Path
    environment: EnvironmentProvider
    auth_status_args: Sequence[str] | None = None
    auth_status_parser: AuthStatusParser | None = None
    _version_checked: bool = field(default=False, init=False, repr=False)
    _version: str | None = field(default=None, init=False, repr=False)
    _version_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    async def version(self) -> str | None:
        async with self._version_lock:
            if self._version_checked:
                return self._version
            self._version_checked = True
            try:
                self.workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
                result = await run_process(
                    [self.executable, "--version"],
                    workspace=self.workspace,
                    timeout_seconds=2,
                    env=self._environment(),
                    inherit_environment=False,
                )
            except (OSError, ProcessExecutionError, ProcessTimeoutError):
                return None
            if result.returncode != 0:
                return None
            self._version = _safe_version(result.stdout, result.stderr)
            return self._version

    async def auth_state(self) -> AuthState:
        if self.auth_status_args is None or self.auth_status_parser is None:
            return AuthState.UNKNOWN
        try:
            self.workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
            result = await run_process(
                [self.executable, *self.auth_status_args],
                workspace=self.workspace,
                timeout_seconds=3,
                env=self._environment(),
                inherit_environment=False,
            )
        except (OSError, ProcessExecutionError, ProcessTimeoutError):
            return AuthState.UNKNOWN
        try:
            state = self.auth_status_parser(result)
            return state if isinstance(state, AuthState) else AuthState.UNKNOWN
        except (TypeError, ValueError):
            return AuthState.UNKNOWN

    def _environment(self) -> Mapping[str, str]:
        environment = self.environment
        return environment() if callable(environment) else environment


def _safe_version(stdout: str, stderr: str) -> str | None:
    for line in (stdout + "\n" + stderr).splitlines():
        candidate = _ANSI_ESCAPE.sub("", line).strip()
        if candidate and _VERSION_PATTERN.fullmatch(candidate):
            return candidate
    return None
