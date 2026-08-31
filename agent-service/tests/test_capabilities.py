from pathlib import Path

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.main import create_app
from app.runners.base import AgentRunner, RunnerRequest, RunnerResult
from app.runners.registry import RunnerRegistry
from app.schemas import AgentName, AuthState, RunnerCapabilities, RunnerModelCapabilities

TOKEN = "a" * 32


class FakeRunner(AgentRunner):
    name = AgentName.ANTIGRAVITY

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
        return RunnerResult(
            payload={"answer": "ok"},
            model_id=request.model_id,
            input_tokens=1,
            output_tokens=2,
            duration_seconds=0.01,
        )


def test_capabilities_are_owned_by_runners_and_do_not_run_generation(tmp_path: Path) -> None:
    settings = Settings(agent_service_token=SecretStr(TOKEN), agent_workspace_root=tmp_path)
    app = create_app(settings, registry=RunnerRegistry([FakeRunner()]))
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
                "models": [
                    {
                        "model_id": "fake-model",
                        "supports_text_input": True,
                        "supports_image_input": False,
                        "supports_structured_output": True,
                        "supports_temperature": False,
                        "supports_max_output_tokens": False,
                    }
                ],
            }
        ]
    }


def test_default_registry_has_no_invented_models(tmp_path: Path) -> None:
    settings = Settings(agent_service_token=SecretStr(TOKEN), agent_workspace_root=tmp_path)
    response = TestClient(create_app(settings)).get(
        "/v1/capabilities", headers={"Authorization": f"Bearer {TOKEN}"}
    )

    assert response.status_code == 200
    assert response.json()["runners"] == [
        {
            "agent": "antigravity",
            "installed": True,
            "version": None,
            "auth_state": "unknown",
            "models": [],
        },
        {
            "agent": "codex",
            "installed": True,
            "version": None,
            "auth_state": "unknown",
            "models": [],
        },
        {
            "agent": "claude",
            "installed": True,
            "version": None,
            "auth_state": "unknown",
            "models": [],
        },
    ]


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
            "models": [],
        }
    ]
