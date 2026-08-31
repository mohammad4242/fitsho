from dataclasses import dataclass
from typing import Protocol

from ..schemas import AgentName
from .schemas import AuthSessionStatus


@dataclass(frozen=True)
class AuthCommand:
    executable: str
    args: tuple[str, ...]
    use_pty: bool
    environment: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ParsedAuthUpdate:
    verification_url: str | None = None
    user_code: str | None = None
    needs_input: bool = False
    input_label: str | None = None
    authenticated: bool = False
    failed: bool = False
    safe_error_message: str | None = None
    press_enter: bool = False


class AgentAuthAdapter(Protocol):
    agent: AgentName
    manual_auth_only: bool

    def command(self) -> AuthCommand: ...

    def allowed_auth_hosts(self) -> frozenset[str]: ...

    def parse_output(self, text: str) -> ParsedAuthUpdate: ...

    def classify_exit(self, returncode: int, final_text: str) -> AuthSessionStatus: ...
