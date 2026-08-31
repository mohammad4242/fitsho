from ...schemas import AgentName
from ..base import AuthCommand, ParsedAuthUpdate
from ..schemas import AuthInputLabel, AuthSessionStatus
from . import parse_browser_handoff

ANTIGRAVITY_AUTH_HOSTS = frozenset({"accounts.google.com"})


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

    def parse_output(self, text: str) -> ParsedAuthUpdate:
        return parse_browser_handoff(
            text,
            allowed_hosts=ANTIGRAVITY_AUTH_HOSTS,
            include_user_code=False,
            input_label=AuthInputLabel.AUTHORIZATION_CODE.value,
        )

    def classify_exit(self, returncode: int, final_text: str) -> AuthSessionStatus:
        del final_text
        return AuthSessionStatus.AUTHENTICATED if returncode == 0 else AuthSessionStatus.FAILED
