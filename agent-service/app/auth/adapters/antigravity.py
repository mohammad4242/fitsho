import re
from collections.abc import Mapping
from pathlib import Path

from ...schemas import AgentName
from ..base import AuthCommand, ParsedAuthUpdate
from ..schemas import AuthInputLabel, AuthSafeErrorMessage, AuthSessionStatus
from . import parse_browser_handoff

ANTIGRAVITY_AUTH_HOSTS = frozenset({"accounts.google.com"})
_GOOGLE_OAUTH_MENU_MARKER = "select login method:"
_OAUTH_FAILURE_PATTERN = re.compile(r"(?i)\btoken\s+exchange\s+failed\b")


class AntigravityAuthAdapter:
    agent = AgentName.ANTIGRAVITY
    manual_auth_only = False

    def __init__(self, executable: str = "agy") -> None:
        self.executable = executable

    def command(self) -> AuthCommand:
        return AuthCommand(
            self.executable,
            (),
            use_pty=True,
            environment=(
                ("SSH_CONNECTION", "sandbox 0 sandbox 0"),
                ("SSH_CLIENT", "sandbox 0 0"),
            ),
        )

    def allowed_auth_hosts(self) -> frozenset[str]:
        return ANTIGRAVITY_AUTH_HOSTS

    def clear_saved_credentials(self, environment: Mapping[str, str]) -> None:
        home = environment.get("HOME")
        if not home:
            return
        token_path = Path(home) / ".gemini" / "antigravity-cli" / "antigravity-oauth-token"
        token_path.unlink(missing_ok=True)

    def saved_credentials_marker(
        self,
        environment: Mapping[str, str],
    ) -> tuple[int, int, int] | None:
        home = environment.get("HOME")
        if not home:
            return None
        token_path = Path(home) / ".gemini" / "antigravity-cli" / "antigravity-oauth-token"
        try:
            if not token_path.is_file():
                return None
            stat = token_path.stat()
        except OSError:
            return None
        if stat.st_size <= 0:
            return None
        return (stat.st_ino, stat.st_mtime_ns, stat.st_size)

    def has_saved_credentials(self, environment: Mapping[str, str]) -> bool:
        return self.saved_credentials_marker(environment) is not None

    def parse_output(self, text: str) -> ParsedAuthUpdate:
        if _OAUTH_FAILURE_PATTERN.search(text):
            return ParsedAuthUpdate(
                failed=True,
                safe_error_message=AuthSafeErrorMessage.FAILED.value,
            )
        update = parse_browser_handoff(
            text,
            allowed_hosts=ANTIGRAVITY_AUTH_HOSTS,
            include_user_code=False,
            input_label=AuthInputLabel.AUTHORIZATION_CODE.value,
        )
        if (
            not update.verification_url
            and not update.failed
            and not update.authenticated
            and _GOOGLE_OAUTH_MENU_MARKER in text.lower()
        ):
            return ParsedAuthUpdate(press_enter=True)
        return update

    def classify_exit(self, returncode: int, final_text: str) -> AuthSessionStatus:
        del final_text
        return AuthSessionStatus.AUTHENTICATED if returncode == 0 else AuthSessionStatus.FAILED
