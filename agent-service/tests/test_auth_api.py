import asyncio
import sys
from collections.abc import Coroutine
from pathlib import Path
from typing import Any

import pytest
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


class ManualOnlyAuthAdapter(FakeAuthAdapter):
    agent = AgentName.ANTIGRAVITY
    manual_auth_only = True


def make_client(tmp_path: Path, script_body: str | None = None) -> tuple[TestClient, AuthManager]:
    script = tmp_path / "fake-auth.py"
    script.write_text(
        script_body or "import time\nprint('READY', flush=True)\ntime.sleep(60)\n",
        encoding="utf-8",
    )
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


def test_auth_routes_never_expose_raw_cli_output_or_sensitive_input(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    client, manager = make_client(
        tmp_path,
        "import sys, time\nprint('READY', flush=True)\n"
        "print('PRIVATE-CLI-OUTPUT', file=sys.stderr, flush=True)\ntime.sleep(60)\n",
    )
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        started = client.post("/v1/auth/start", headers=headers, json={"agent": "codex"})
        assert started.status_code == 200
        response = client.get(f"/v1/auth/{started.json()['session_id']}", headers=headers)
        assert response.status_code == 200
        assert "PRIVATE-CLI-OUTPUT" not in response.text
        assert "authorization code" not in response.text
        assert "AGENT_SERVICE_TOKEN" not in response.text
        assert "PRIVATE-CLI-OUTPUT" not in caplog.text
        client.delete(f"/v1/auth/{started.json()['session_id']}", headers=headers)
    finally:
        run(manager.shutdown())


def test_auth_input_is_only_accepted_for_an_existing_waiting_process(
    tmp_path: Path,
) -> None:
    client, manager = make_client(tmp_path)
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        missing = "00000000-0000-0000-0000-000000000000"
        response = client.post(
            f"/v1/auth/{missing}/input",
            headers=headers,
            json={"value": "safe"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "auth_session_not_found"

        started = client.post("/v1/auth/start", headers=headers, json={"agent": "codex"})
        session_id = started.json()["session_id"]
        unexpected = client.post(
            f"/v1/auth/{session_id}/input",
            headers=headers,
            json={"value": "safe"},
        )
        assert unexpected.status_code == 409
        assert unexpected.json()["error"]["code"] == "auth_input_not_expected"

        invalid = client.post(
            f"/v1/auth/{session_id}/input",
            headers=headers,
            json={"value": "x" * 4097},
        )
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "invalid_request"
        client.delete(f"/v1/auth/{session_id}", headers=headers)
    finally:
        run(manager.shutdown())


def test_manual_only_agent_returns_safe_capability_boundary(tmp_path: Path) -> None:
    script = tmp_path / "manual-auth.py"
    script.write_text("import time\ntime.sleep(60)\n", encoding="utf-8")
    manager = AuthManager(
        {AgentName.ANTIGRAVITY: ManualOnlyAuthAdapter(script)},
        workspace=tmp_path,
    )
    settings = Settings(agent_service_token=SecretStr(TOKEN), agent_workspace_root=tmp_path)
    try:
        client = TestClient(create_app(settings, auth_manager=manager))
        response = client.post(
            "/v1/auth/start",
            headers={"Authorization": f"Bearer {TOKEN}"},
            json={"agent": "antigravity"},
        )

        assert response.status_code == 409
        assert response.json()["error"] == {
            "code": "auth_manual_only",
            "message": "authentication is unavailable",
            "request_id": response.json()["error"]["request_id"],
        }
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


def test_active_auth_cancellation_is_idempotent_and_safe(tmp_path: Path) -> None:
    client, manager = make_client(tmp_path)
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        started = client.post("/v1/auth/start", headers=headers, json={"agent": "codex"})
        assert started.status_code == 200

        canceled = client.post(
            "/v1/auth/cancel-active",
            headers=headers,
            json={"agent": "codex"},
        )
        assert canceled.status_code == 200
        assert canceled.json() == {"agent": "codex", "canceled": True}

        repeated = client.post(
            "/v1/auth/cancel-active",
            headers=headers,
            json={"agent": "codex"},
        )
        assert repeated.status_code == 200
        assert repeated.json() == {"agent": "codex", "canceled": False}
        assert "session_id" not in canceled.text
    finally:
        run(manager.shutdown())


def test_auth_telemetry_uses_only_non_sensitive_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records: list[dict[str, object]] = []
    monkeypatch.setattr("app.main.emit_log", lambda fields: records.append(dict(fields)))
    client, manager = make_client(tmp_path)
    try:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        started = client.post("/v1/auth/start", headers=headers, json={"agent": "codex"})
        session_id = started.json()["session_id"]
        client.get(f"/v1/auth/{session_id}", headers=headers)
        client.delete(f"/v1/auth/{session_id}", headers=headers)

        auth_records = [
            record
            for record in records
            if str(record.get("endpoint", "")).startswith("/v1/auth/")
        ]
        assert auth_records
        allowed = {"request_id", "endpoint", "agent", "status", "duration_ms", "error_code"}
        for record in auth_records:
            assert set(record) <= allowed
        serialized = str(auth_records)
        assert "https://auth.openai.com" not in serialized
        assert "ABCD-EFGH" not in serialized
        assert "AGENT_SERVICE_TOKEN" not in serialized
        assert "PRIVATE-CLI-OUTPUT" not in serialized
    finally:
        run(manager.shutdown())
