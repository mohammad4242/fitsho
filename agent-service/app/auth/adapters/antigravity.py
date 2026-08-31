from ...schemas import AgentName
from ..base import AuthCommand, ParsedAuthUpdate
from ..schemas import AuthSafeErrorMessage, AuthSessionStatus


class AntigravityAuthAdapter:
    agent = AgentName.ANTIGRAVITY
    manual_auth_only = True

    def __init__(self, executable: str = "agy") -> None:
        self.executable = executable

    def command(self) -> AuthCommand:
        return AuthCommand(self.executable, (), use_pty=True)

    def allowed_auth_hosts(self) -> frozenset[str]:
        return frozenset()

    def parse_output(self, text: str) -> ParsedAuthUpdate:
        del text
        return ParsedAuthUpdate(
            failed=True,
            safe_error_message=AuthSafeErrorMessage.UNAVAILABLE.value,
        )

    def classify_exit(self, returncode: int, final_text: str) -> AuthSessionStatus:
        del returncode, final_text
        return AuthSessionStatus.FAILED
