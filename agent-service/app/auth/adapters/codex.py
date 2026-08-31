from ...schemas import AgentName
from ..base import AuthCommand, ParsedAuthUpdate
from ..schemas import AuthSessionStatus
from . import CODEX_AUTH_HOSTS, parse_browser_handoff


class CodexAuthAdapter:
    agent = AgentName.CODEX
    manual_auth_only = False

    def __init__(self, executable: str = "codex") -> None:
        self.executable = executable

    def command(self) -> AuthCommand:
        return AuthCommand(
            self.executable,
            ("login", "--device-auth"),
            use_pty=False,
        )

    def allowed_auth_hosts(self) -> frozenset[str]:
        return CODEX_AUTH_HOSTS

    def parse_output(self, text: str) -> ParsedAuthUpdate:
        return parse_browser_handoff(
            text,
            allowed_hosts=CODEX_AUTH_HOSTS,
            include_user_code=True,
        )

    def classify_exit(self, returncode: int, final_text: str) -> AuthSessionStatus:
        del final_text
        return AuthSessionStatus.AUTHENTICATED if returncode == 0 else AuthSessionStatus.FAILED
