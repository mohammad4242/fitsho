from ...schemas import AgentName
from ..base import AuthCommand, ParsedAuthUpdate
from ..schemas import AuthSessionStatus
from . import CLAUDE_AUTH_HOSTS, parse_browser_handoff


class ClaudeAuthAdapter:
    agent = AgentName.CLAUDE
    manual_auth_only = False

    def __init__(self, executable: str = "claude") -> None:
        self.executable = executable

    def command(self) -> AuthCommand:
        return AuthCommand(
            self.executable,
            ("auth", "login"),
            use_pty=False,
        )

    def allowed_auth_hosts(self) -> frozenset[str]:
        return CLAUDE_AUTH_HOSTS

    def parse_output(self, text: str) -> ParsedAuthUpdate:
        return parse_browser_handoff(
            text,
            allowed_hosts=CLAUDE_AUTH_HOSTS,
            include_user_code=False,
        )

    def classify_exit(self, returncode: int, final_text: str) -> AuthSessionStatus:
        del final_text
        return AuthSessionStatus.AUTHENTICATED if returncode == 0 else AuthSessionStatus.FAILED
