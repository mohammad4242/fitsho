import asyncio
import sys
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.auth.base import AuthCommand, ParsedAuthUpdate
from app.auth.manager import AuthManager
from app.auth.schemas import AuthSessionStatus
from app.config import Settings
from app.main import create_app
from app.schemas import AgentName

TOKEN = "a" * 32


def run[T](coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


class FakeAuthAdapter:
    agent = AgentName.CODEX
    manual_auth_only = False

    def __init__(self, script: Path) -> None:
        self.script = script

    def command(self) -> AuthCommand:
        return AuthCommand(sys.executable, (str(self.script),), use_pty=False)

    def allowed_auth_hosts(self) -> frozenset[str]:
        return frozenset({"auth.openai.com"})

    def parse_output(self, text: str) -> ParsedAuthUpdate:
        if "READY" in text:
            return ParsedAuthUpdate(
                verification_url="https://auth.openai.com/device?state=opaque",
                user_code="ABCD-EFGH",
            )
        return ParsedAuthUpdate()

    def classify_exit(self, returncode: int, final_text: str) -> AuthSessionStatus:
        del final_text
        return AuthSessionStatus.AUTHENTICATED if returncode == 0 else AuthSessionStatus.FAILED


def make_client(tmp_path: Path) -> tuple[TestClient, AuthManager]:
    script = tmp_path / "fake-auth.py"
    script.write_text("import time\nprint('READY', flush=True)\ntime.sleep(60)\n", encoding="utf-8")
    manager = AuthManager(
        {AgentName.CODEX: FakeAuthAdapter(script)},
        workspace=tmp_path,
        environment={"PATH": "/usr/bin"},
    )
    settings = Settings(agent_service_token=SecretStr(TOKEN), agent_workspace_root=tmp_path)
    return TestClient(create_app(settings, auth_manager=manager)), manager


def test_auth_routes_require_bearer_and_reject_unknown_agent(tmp_path: Path) -> None:
    client, manager = make_client(tmp_path)
    try:
        assert client.post("/v1/auth/start", json={"agent": "codex"}).status_code == 401
        response = client.post(
            "/v1/auth/start",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={"agent": "unknown"},
        )
        assert response.status_code == 422
        assert "unknown" not in response.text
    finally:
        run(manager.shutdown())


def test_auth_start_poll_duplicate_and_cancel_use_safe_contract(tmp_path: Path) -> None:
    client, manager = make_client(tmp_path)
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        started = client.post("/v1/auth/start", headers=headers, json={"agent": "codex"})
        assert started.status_code == 200
        body = started.json()
        assert set(body) == {
            "session_id",
            "agent",
            "status",
            "verification_url",
            "user_code",
            "input_label",
            "expires_at",
            "safe_error_message",
        }
        assert "private" not in started.text
        duplicate = client.post("/v1/auth/start", headers=headers, json={"agent": "codex"})
        assert duplicate.status_code == 409
        assert duplicate.json()["error"]["code"] == "auth_in_progress"
        current = client.get(f"/v1/auth/{body['session_id']}", headers=headers)
        assert current.status_code == 200
        assert current.json()["status"] in {"starting", "waiting_for_user"}
        canceled = client.delete(f"/v1/auth/{body['session_id']}", headers=headers)
        assert canceled.status_code == 200
        assert canceled.json()["status"] == "canceled"
        assert client.get(f"/v1/auth/{body['session_id']}", headers=headers).status_code == 200
    finally:
        run(manager.shutdown())
