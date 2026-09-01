from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.main import create_app
from app.runners.base import RunnerError, RunnerRequest, RunnerResult
from app.runners.registry import RunnerRegistry
from app.schemas import AgentName, AuthState, RunnerCapabilities, RunnerModelCapabilities
from app.workspace import RequestWorkspace

TOKEN = "a" * 32


class FakeRunner:
    name = AgentName.ANTIGRAVITY

    def __init__(self, *, error: str | None = None) -> None:
        self.requests: list[RunnerRequest] = []
        self.error = error

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
        self.requests.append(request)
        if self.error:
            raise RunnerError(self.error, "internal detail must not escape")
        response_payload = {"ok": True} if request.schema_name == "agent_test" else {"answer": "ok"}
        return RunnerResult(
            payload=response_payload,
            model_id=request.model_id,
            input_tokens=3,
            output_tokens=4,
            duration_seconds=0.2,
        )


def payload() -> dict[str, object]:
    return {
        "agent": "antigravity",
        "model_id": "fake-model",
        "system_prompt": "Return an answer.",
        "input_payload": {"question": "hello"},
        "response_schema": {
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
        },
        "schema_name": "answer",
        "temperature": 0.2,
        "max_output_tokens": 100,
        "timeout_seconds": 5,
    }


def make_client(tmp_path: Path, runner: FakeRunner) -> TestClient:
    settings = Settings(agent_service_token=SecretStr(TOKEN), agent_workspace_root=tmp_path)
    return TestClient(create_app(settings, registry=RunnerRegistry([runner])))


def test_generate_validates_capability_and_returns_normalized_contract(tmp_path: Path) -> None:
    runner = FakeRunner()
    response = make_client(tmp_path, runner).post(
        "/v1/generate", json=payload(), headers={"Authorization": f"Bearer {TOKEN}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["payload"] == {"answer": "ok"}
    assert body["agent"] == "antigravity"
    assert body["model_id"] == "fake-model"
    assert body["input_tokens"] == 3
    assert body["output_tokens"] == 4
    assert body["request_id"]
    assert len(runner.requests) == 1
    assert runner.requests[0].image_paths == ()
    assert runner.requests[0].system_prompt == payload()["system_prompt"]
    assert runner.requests[0].input_payload == payload()["input_payload"]
    assert runner.requests[0].response_schema == payload()["response_schema"]
    assert runner.requests[0].schema_name == payload()["schema_name"]
    assert runner.requests[0].temperature == payload()["temperature"]
    assert runner.requests[0].max_output_tokens == payload()["max_output_tokens"]
    assert list(tmp_path.iterdir()) == []


def test_generate_rejects_unknown_model_without_running(tmp_path: Path) -> None:
    runner = FakeRunner()
    request = payload()
    request["model_id"] = "not-configured"
    response = make_client(tmp_path, runner).post(
        "/v1/generate", json=request, headers={"Authorization": f"Bearer {TOKEN}"}
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"
    assert len(runner.requests) == 0
    assert "not-configured" not in response.text


def test_generate_maps_runner_errors_to_safe_envelope(tmp_path: Path) -> None:
    runner = FakeRunner(error="timeout")
    response = make_client(tmp_path, runner).post(
        "/v1/generate", json=payload(), headers={"Authorization": f"Bearer {TOKEN}"}
    )

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "timeout"
    assert response.json()["error"]["message"] == "runner timed out"
    assert "internal detail" not in response.text
    assert list(tmp_path.iterdir()) == []


def test_test_endpoint_uses_same_registry_and_contract(tmp_path: Path) -> None:
    runner = FakeRunner()
    response = make_client(tmp_path, runner).post(
        "/v1/test",
        json={"agent": "antigravity", "model_id": "fake-model"},
        headers={"Authorization": f"Bearer {TOKEN}"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert runner.requests[0].schema_name == "agent_test"


def test_generate_rejects_invalid_response_schema_before_running(tmp_path: Path) -> None:
    runner = FakeRunner()
    request = payload()
    request["response_schema"] = {"type": "not-a-schema-type"}

    response = make_client(tmp_path, runner).post(
        "/v1/generate", json=request, headers={"Authorization": f"Bearer {TOKEN}"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert runner.requests == []


def test_generate_rejects_runner_payload_that_breaks_requested_schema(
    tmp_path: Path,
) -> None:
    class BadRunner(FakeRunner):
        async def run(self, request: RunnerRequest) -> RunnerResult:
            self.requests.append(request)
            return RunnerResult(
                payload={"wrong": True},
                model_id=request.model_id,
                input_tokens=None,
                output_tokens=None,
                duration_seconds=0.1,
            )

    runner = BadRunner()
    response = make_client(tmp_path, runner).post(
        "/v1/generate", json=payload(), headers={"Authorization": f"Bearer {TOKEN}"}
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "invalid_output"


def test_generate_rejects_runner_model_identity_mismatch(tmp_path: Path) -> None:
    class MismatchedRunner(FakeRunner):
        async def run(self, request: RunnerRequest) -> RunnerResult:
            self.requests.append(request)
            return RunnerResult(
                payload={"answer": "ok"},
                model_id="different-model",
                input_tokens=None,
                output_tokens=None,
                duration_seconds=0.1,
            )

    response = make_client(tmp_path, MismatchedRunner()).post(
        "/v1/generate", json=payload(), headers={"Authorization": f"Bearer {TOKEN}"}
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "invalid_output"


def test_generate_maps_unexpected_runner_failure_to_safe_error(tmp_path: Path) -> None:
    class ExplodingRunner(FakeRunner):
        async def run(self, request: RunnerRequest) -> RunnerResult:
            raise RuntimeError("secret runner internals")

    response = make_client(tmp_path, ExplodingRunner()).post(
        "/v1/generate", json=payload(), headers={"Authorization": f"Bearer {TOKEN}"}
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_unavailable"
    assert "secret runner internals" not in response.text


def test_generate_requires_text_capability(tmp_path: Path) -> None:
    class ImageOnlyRunner(FakeRunner):
        async def capabilities(self) -> RunnerCapabilities:
            capabilities = await super().capabilities()
            model = capabilities.models[0].model_copy(update={"supports_text_input": False})
            return capabilities.model_copy(update={"models": [model]})

    runner = ImageOnlyRunner()
    response = make_client(tmp_path, runner).post(
        "/v1/generate", json=payload(), headers={"Authorization": f"Bearer {TOKEN}"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert runner.requests == []


def test_generate_maps_workspace_cleanup_failure_to_safe_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing_exit(
        self: RequestWorkspace, exc_type: object, exc_value: object, traceback: object
    ) -> None:
        raise OSError("sensitive cleanup path")

    monkeypatch.setattr(RequestWorkspace, "__aexit__", failing_exit)
    response = make_client(tmp_path, FakeRunner()).post(
        "/v1/generate", json=payload(), headers={"Authorization": f"Bearer {TOKEN}"}
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "provider_unavailable"
    assert "sensitive cleanup path" not in response.text
