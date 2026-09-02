from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.main import create_app
from app.runners.base import AgentRunner, RunnerError, RunnerRequest, RunnerResult
from app.runners.registry import RunnerRegistry
from app.schemas import AgentName, AuthState, RunnerCapabilities, RunnerModelCapabilities

TOKEN = "a" * 32


class FakeRunner(AgentRunner):
    name = AgentName.ANTIGRAVITY

    def __init__(self) -> None:
        self.run_calls = 0

    async def capabilities(self) -> RunnerCapabilities:
        return RunnerCapabilities(
            agent=self.name,
            installed=True,
            auth_state=AuthState.UNKNOWN,
            models=[
                RunnerModelCapabilities(
                    model_id="fake-model",
                    supports_text_input=True,
                    supports_image_input=False,
                    supports_structured_output=True,
                )
            ],
        )

    async def run(self, request: RunnerRequest) -> RunnerResult:
        self.run_calls += 1
        return RunnerResult(
            payload={"ok": True},
            model_id=request.model_id,
            input_tokens=1,
            output_tokens=2,
            duration_seconds=0.01,
        )


def test_capabilities_are_owned_by_runners_and_do_not_run_generation(tmp_path: Path) -> None:
    settings = Settings(agent_service_token=SecretStr(TOKEN), agent_workspace_root=tmp_path)
    runner = FakeRunner()
    app = create_app(settings, registry=RunnerRegistry([runner]))
    response = TestClient(app).get(
        "/v1/capabilities", headers={"Authorization": f"Bearer {TOKEN}"}
    )

    assert response.status_code == 200
    assert response.json() == {
        "runners": [
            {
                "agent": "antigravity",
                "installed": True,
                "version": None,
                "auth_state": "unknown",
                "auth_mode": "unknown",
                "models": [
                    {
                        "model_id": "fake-model",
                        "supports_text_input": True,
                        "supports_image_input": False,
                        "supports_structured_output": True,
                        "supports_live_web": False,
                        "supports_temperature": False,
                        "supports_max_output_tokens": False,
                    }
                ],
            }
        ]
    }
    assert runner.run_calls == 0


def test_default_registry_has_no_invented_models(tmp_path: Path) -> None:
    settings = Settings(agent_service_token=SecretStr(TOKEN), agent_workspace_root=tmp_path)
    response = TestClient(create_app(settings)).get(
        "/v1/capabilities", headers={"Authorization": f"Bearer {TOKEN}"}
    )

    assert response.status_code == 200
    runners = {runner["agent"]: runner for runner in response.json()["runners"]}
    assert set(runners) == {"antigravity", "codex", "claude"}
    assert runners["antigravity"]["version"] == "1.1.22"
    assert runners["antigravity"]["auth_mode"] == "browser_link"
    assert runners["codex"]["auth_mode"] == "browser_link"
    assert runners["claude"]["auth_mode"] == "browser_link"
    assert runners["codex"]["version"] == "codex-cli 0.151.0"
    assert runners["claude"]["version"] == "2.1.220 (Claude Code)"
    assert all(runner["installed"] is True for runner in runners.values())
    assert all(runner["models"] == [] for runner in runners.values())
    assert runners["antigravity"]["auth_state"] == "unknown"
    assert runners["codex"]["auth_state"] in {
        "authenticated",
        "unauthenticated",
        "unknown",
    }
    assert runners["claude"]["auth_state"] in {
        "authenticated",
        "unauthenticated",
        "unknown",
    }


def test_capability_probe_failure_is_reported_without_a_500(tmp_path: Path) -> None:
    class BrokenRunner(FakeRunner):
        async def capabilities(self) -> RunnerCapabilities:
            raise RuntimeError("private capability failure")

    settings = Settings(agent_service_token=SecretStr(TOKEN), agent_workspace_root=tmp_path)
    response = TestClient(create_app(settings, registry=RunnerRegistry([BrokenRunner()]))).get(
        "/v1/capabilities", headers={"Authorization": f"Bearer {TOKEN}"}
    )

    assert response.status_code == 200
    assert response.json()["runners"] == [
        {
            "agent": "antigravity",
            "installed": False,
            "version": None,
            "auth_state": "unknown",
            "auth_mode": "unknown",
            "models": [],
        }
    ]


def test_successful_test_marks_runner_authenticated_without_model_quota_probe(
    tmp_path: Path,
) -> None:
    settings = Settings(agent_service_token=SecretStr(TOKEN), agent_workspace_root=tmp_path)
    runner = FakeRunner()
    registry = RunnerRegistry([runner])
    app = create_app(settings, registry=registry)
    client = TestClient(app)

    response = client.post(
        "/v1/test",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={"agent": "antigravity", "model_id": "fake-model"},
    )

    assert response.status_code == 200
    assert runner.run_calls == 1
    capabilities = client.get(
        "/v1/capabilities", headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert capabilities.json()["runners"][0]["auth_state"] == "authenticated"


def test_unauthorized_test_marks_runner_unauthenticated(tmp_path: Path) -> None:
    class UnauthorizedRunner(FakeRunner):
        async def run(self, request: RunnerRequest) -> RunnerResult:
            del request
            raise RunnerError("unauthorized", "private runner error")

    settings = Settings(agent_service_token=SecretStr(TOKEN), agent_workspace_root=tmp_path)
    runner = UnauthorizedRunner()
    registry = RunnerRegistry([runner])
    client = TestClient(create_app(settings, registry=registry))

    response = client.post(
        "/v1/test",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={"agent": "antigravity", "model_id": "fake-model"},
    )

    assert response.status_code == 401
    assert "private runner error" not in response.text
    capabilities = client.get(
        "/v1/capabilities", headers={"Authorization": f"Bearer {TOKEN}"}
    )
    assert capabilities.json()["runners"][0]["auth_state"] == "unauthenticated"
