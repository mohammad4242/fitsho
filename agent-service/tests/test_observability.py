import json
import logging
from pathlib import Path

from _pytest.logging import LogCaptureFixture
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.main import create_app
from app.observability import build_log_record
from app.runners.base import RunnerRequest, RunnerResult
from app.runners.registry import RunnerRegistry
from app.schemas import AgentName, AuthState, RunnerCapabilities, RunnerModelCapabilities


def test_log_record_redacts_sensitive_runner_data() -> None:
    record = build_log_record(
        request_id="req-1", agent="codex", model="gpt-test", endpoint="/v1/generate",
        duration_ms=12.5, status="error", error_code="provider_unavailable",
        input_bytes=42, image_count=1, input_tokens=3, output_tokens=5,
        prompt="do not log this prompt", input_payload={"secret": "do not log this payload"},
        image_paths=["/private/image.jpg"], authorization="Bearer secret",
        token="secret-token", credentials={"password": "secret"}, stderr="private stderr",
    )
    assert record == {
        "request_id": "req-1", "agent": "codex", "model": "gpt-test",
        "endpoint": "/v1/generate", "duration_ms": 12.5, "status": "error",
        "error_code": "provider_unavailable", "input_bytes": 42, "image_count": 1,
        "input_tokens": 3, "output_tokens": 5,
    }


def test_agent_service_logger_emits_info_in_runtime() -> None:
    from app.observability import _LOGGER

    assert _LOGGER.isEnabledFor(logging.INFO)
    assert _LOGGER.handlers


def test_http_logging_is_json_and_contains_only_request_metrics(caplog: LogCaptureFixture) -> None:
    app = create_app(Settings(agent_service_token=SecretStr("a" * 32)))
    with caplog.at_level("INFO", logger="fitsho.agent_service"):
        response = TestClient(app).get("/healthz")

    assert response.status_code == 200
    record = json.loads(caplog.records[-1].message)
    assert record["endpoint"] == "/healthz"
    assert record["status"] == 200
    assert set(record) <= {
        "request_id", "agent", "model", "endpoint", "task_kind", "duration_ms",
        "status", "error_code", "input_bytes", "image_count", "input_tokens", "output_tokens",
    }


def test_generation_logging_includes_safe_agent_model_and_usage(
    tmp_path: Path, caplog: LogCaptureFixture
) -> None:
    class FakeRunner:
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
                input_tokens=7,
                output_tokens=4,
                duration_seconds=0.1,
            )

    request = {
        "agent": "antigravity",
        "model_id": "fake-model",
        "system_prompt": "private prompt",
        "input_payload": {"secret": "private payload"},
        "response_schema": {"type": "object", "properties": {"answer": {"type": "string"}}},
        "schema_name": "answer",
        "temperature": 0,
        "max_output_tokens": 32,
        "timeout_seconds": 5,
    }
    app = create_app(
        Settings(agent_service_token=SecretStr("a" * 32), agent_workspace_root=tmp_path),
        registry=RunnerRegistry([FakeRunner()]),
    )
    with caplog.at_level("INFO", logger="fitsho.agent_service"):
        response = TestClient(app).post(
            "/v1/generate", json=request, headers={"Authorization": "Bearer " + "a" * 32}
        )

    assert response.status_code == 200
    record = json.loads(caplog.records[-1].message)
    assert record["agent"] == "antigravity"
    assert record["model"] == "fake-model"
    assert record["task_kind"] == "generate"
    assert record["input_tokens"] == 7
    assert record["output_tokens"] == 4
    assert "private prompt" not in caplog.text
    assert "private payload" not in caplog.text
