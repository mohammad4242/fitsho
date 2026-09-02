import os
from collections.abc import Mapping
from pathlib import Path

from ...process import ProcessExecutionError, ProcessTimeoutError, run_process
from ...schemas import AgentName, AuthState
from ..base import AuthCommand, ParsedAuthUpdate
from ..schemas import AuthSessionStatus
from . import CODEX_AUTH_HOSTS, parse_browser_handoff


class CodexAuthAdapter:
    agent = AgentName.CODEX
    manual_auth_only = False
    _AUTH_RELATIVE_PATH = Path(".codex") / "auth.json"
    _BACKUP_NAME = ".auth.json.fitsho-backup"

    def __init__(self, executable: str = "codex", *, workspace: Path | None = None) -> None:
        self.executable = executable
        self.workspace = workspace

    async def probe_auth_state(self, environment: Mapping[str, str]) -> AuthState:
        if self.workspace is None:
            return AuthState.UNKNOWN
        try:
            self.workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
            result = await run_process(
                [self.executable, "login", "status"],
                workspace=self.workspace,
                timeout_seconds=3,
                env=environment,
                inherit_environment=False,
            )
        except (OSError, ProcessExecutionError, ProcessTimeoutError, RuntimeError, ValueError):
            return AuthState.UNKNOWN
        text = (result.stdout + "\n" + result.stderr).lower()
        if result.returncode == 0:
            return AuthState.AUTHENTICATED
        if "not logged in" in text or "not authenticated" in text:
            return AuthState.UNAUTHENTICATED
        return AuthState.UNKNOWN

    def command(self) -> AuthCommand:
        return AuthCommand(
            self.executable,
            ("login", "--device-auth"),
            use_pty=False,
        )

    def allowed_auth_hosts(self) -> frozenset[str]:
        return CODEX_AUTH_HOSTS

    def auth_path(self, environment: Mapping[str, str]) -> Path:
        home = environment.get("HOME")
        return Path(home or ".") / self._AUTH_RELATIVE_PATH

    def backup_path(self, environment: Mapping[str, str]) -> Path:
        return self.auth_path(environment).with_name(self._BACKUP_NAME)

    def saved_credentials_marker(
        self, environment: Mapping[str, str]
    ) -> tuple[int, int, int] | None:
        if not environment.get("HOME"):
            return None
        path = self.auth_path(environment)
        try:
            if not path.is_file():
                return None
            stat = path.stat()
        except OSError:
            return None
        if stat.st_size <= 0:
            return None
        return (stat.st_ino, stat.st_mtime_ns, stat.st_size)

    def has_saved_credentials(self, environment: Mapping[str, str]) -> bool:
        return self.saved_credentials_marker(environment) is not None

    def backup_saved_credentials(self, environment: Mapping[str, str]) -> None:
        if not environment.get("HOME"):
            return
        source = self.auth_path(environment)
        if not self.has_saved_credentials(environment):
            return
        backup = self.backup_path(environment)
        backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        data = source.read_bytes()
        temporary = backup.with_name(f".{backup.name}.tmp")
        try:
            temporary.write_bytes(data)
            os.chmod(temporary, 0o600)
            os.replace(temporary, backup)
        finally:
            temporary.unlink(missing_ok=True)

    def clear_saved_credentials(self, environment: Mapping[str, str]) -> None:
        if not environment.get("HOME"):
            return
        self.auth_path(environment).unlink(missing_ok=True)

    def restore_saved_credentials(self, environment: Mapping[str, str]) -> None:
        if not environment.get("HOME"):
            return
        backup = self.backup_path(environment)
        if not backup.is_file():
            return
        target = self.auth_path(environment)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = target.with_name(f".{target.name}.tmp")
        try:
            temporary.write_bytes(backup.read_bytes())
            os.chmod(temporary, 0o600)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        backup.unlink(missing_ok=True)

    def finalize_saved_credentials(self, environment: Mapping[str, str]) -> None:
        if not environment.get("HOME"):
            return
        self.backup_path(environment).unlink(missing_ok=True)

    def recover_saved_credentials(self, environment: Mapping[str, str]) -> None:
        # A leftover backup means the previous auth process was interrupted
        # before the manager could settle it. Prefer the known-good credential.
        self.restore_saved_credentials(environment)

    def parse_output(self, text: str) -> ParsedAuthUpdate:
        return parse_browser_handoff(
            text,
            allowed_hosts=CODEX_AUTH_HOSTS,
            include_user_code=True,
        )

    def classify_exit(self, returncode: int, final_text: str) -> AuthSessionStatus:
        del final_text
        return AuthSessionStatus.AUTHENTICATED if returncode == 0 else AuthSessionStatus.FAILED
