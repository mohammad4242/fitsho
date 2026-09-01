import asyncio
import json
import os
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import pytest

from app.process import ProcessResult, ProcessTimeoutError
from app.runners.antigravity import AntigravityRunner
from app.runners.base import RunnerError, RunnerRequest
from app.schemas import AgentName


def run[T](coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coro)


def make_request(
    *,
    image_paths: tuple[Path, ...] = (),
    response_schema: dict[str, Any] | None = None,
    effort: str | None = None,
) -> RunnerRequest:
    return RunnerRequest(
        model_id="gemini-test",
        system_prompt="Return a concise answer.",
        input_payload={"question": "hello"},
        response_schema=response_schema or {"type": "object", "required": ["answer"]},
        schema_name="answer",
        temperature=0.2,
        max_output_tokens=300,
        timeout_seconds=4,
        image_paths=image_paths,
        effort=effort,
    )


def fake_process(
    stdout: str, *, returncode: int = 0, stderr: str = ""
) -> Callable[..., Coroutine[Any, Any, ProcessResult]]:
    async def runner(*args: Any, **kwargs: Any) -> ProcessResult:
        return ProcessResult(returncode=returncode, stdout=stdout, stderr=stderr)

    return runner


def success_output(
    *,
    payload: dict[str, Any] | None = None,
    structured: bool = False,
    usage: dict[str, Any] | None = None,
    duration: float | None = None,
) -> str:
    payload = payload or {"answer": "ok"}
    outer: dict[str, Any] = {
        "status": "SUCCESS",
        "usage": usage or {"input_tokens": 11, "output_tokens": 7},
    }
    if structured:
        outer["structured_output"] = payload
    else:
        outer["response"] = json.dumps(payload)
    if duration is not None:
        outer["duration_seconds"] = duration
    return json.dumps(outer)


def test_capabilities_default_to_text_and_no_image_support(tmp_path: Path) -> None:
    executable = tmp_path / "agy"
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(executable.stat().st_mode | os.X_OK)
    capabilities = run(
        AntigravityRunner(
            workspace=tmp_path,
            executable=str(executable),
            configured_models=("gemini-test",),
        ).capabilities()
    )

    assert capabilities.agent is AgentName.ANTIGRAVITY
    assert capabilities.installed is True
    assert [model.model_id for model in capabilities.models] == ["gemini-test"]
    assert capabilities.models[0].supports_text_input is True
    assert capabilities.models[0].supports_image_input is False
    assert capabilities.models[0].supports_structured_output is True


def test_capabilities_discover_models_when_configuration_is_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "agy"
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(executable.stat().st_mode | os.X_OK)

    async def fake_models(command: list[str], **kwargs: Any) -> ProcessResult:
        del kwargs
        assert command == [str(executable), "models"]
        return ProcessResult(
            0,
            "gemini-3.7-flash-high  Gemini 3.7 Flash (High)\n",
            "",
        )

    import app.runners.antigravity as antigravity

    monkeypatch.setattr(antigravity, "run_process", fake_models)
    capabilities = run(
        AntigravityRunner(workspace=tmp_path, executable=str(executable)).capabilities()
    )

    assert capabilities.profiles is not None
    assert capabilities.profiles[0].profile_id == "antigravity-gemini-3.7-flash-high"


def test_capabilities_mark_missing_executable_uninstalled(tmp_path: Path) -> None:
    capabilities = run(
        AntigravityRunner(
            workspace=tmp_path,
            executable=str(tmp_path / "missing-agy"),
            configured_models=("gemini-test",),
        ).capabilities()
    )

    assert capabilities.installed is False


def test_run_parses_structured_output_and_uses_exact_model_argv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    async def fake_run_process(command: list[str], **kwargs: Any) -> ProcessResult:
        calls.append((command, kwargs))
        schema_path = Path(command[command.index("--json-schema") + 1])
        assert schema_path.is_relative_to(tmp_path)
        assert json.loads(schema_path.read_text()) == make_request().response_schema
        return ProcessResult(0, success_output(structured=True, duration=1.25), "")

    import app.runners.antigravity as antigravity

    monkeypatch.setattr(antigravity, "run_process", fake_run_process)
    result = run(AntigravityRunner(workspace=tmp_path, executable="agy-test").run(make_request()))

    assert result.payload == {"answer": "ok"}
    assert result.model_id == "gemini-test"
    assert result.input_tokens == 11
    assert result.output_tokens == 7
    assert result.duration_seconds == 1.25
    assert len(calls) == 1
    command, kwargs = calls[0]
    assert command[0] == "agy-test"
    assert command[1] == "--print"
    assert command[3:5] == ["--output-format", "json"]
    assert command[5] == "--json-schema"
    assert command[-4:] == [
        "--model",
        "gemini-test",
        "--sandbox",
        "--dangerously-skip-permissions",
    ]
    assert "shell" not in kwargs
    assert kwargs["workspace"] == tmp_path


def test_profile_effort_is_passed_to_agy_and_thinking_maps_to_high(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    async def fake_run_process(command: list[str], **kwargs: Any) -> ProcessResult:
        del kwargs
        calls.append(command)
        return ProcessResult(0, success_output(structured=True), "")

    import app.runners.antigravity as antigravity

    monkeypatch.setattr(antigravity, "run_process", fake_run_process)
    run(
        AntigravityRunner(workspace=tmp_path).run(
            make_request(),
        )
    )
    assert calls

    calls.clear()
    run(AntigravityRunner(workspace=tmp_path).run(make_request(effort="thinking")))
    command = calls[0]
    assert command[command.index("--effort") + 1] == "high"
    assert command[-1] == "--dangerously-skip-permissions"


def test_model_discovery_reuses_last_successful_catalog_on_transient_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = tmp_path / "agy"
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(executable.stat().st_mode | os.X_OK)
    outputs = iter(
        [
            ProcessResult(0, "gemini-3.7-flash-high  Gemini 3.7 Flash (High)\n", ""),
            ProcessResult(1, "", "Please sign in to view available models."),
        ]
    )

    async def fake_models(command: list[str], **kwargs: Any) -> ProcessResult:
        del command, kwargs
        return next(outputs)

    import app.runners.antigravity as antigravity

    monkeypatch.setattr(antigravity, "run_process", fake_models)
    runner = AntigravityRunner(workspace=tmp_path, executable=str(executable))
    first = run(runner.capabilities())
    runner._profiles_cached_at -= 61
    second = run(runner.capabilities())
    assert [profile.profile_id for profile in first.profiles or []] == [
        "antigravity-gemini-3.7-flash-high"
    ]
    assert [profile.profile_id for profile in second.profiles or []] == [
        "antigravity-gemini-3.7-flash-high"
    ]


def test_runner_does_not_pass_agent_service_secrets_to_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    async def fake_run_process(command: list[str], **kwargs: Any) -> ProcessResult:
        captured.update(kwargs)
        return ProcessResult(0, success_output(structured=True), "")

    import app.runners.antigravity as antigravity

    monkeypatch.setenv("AGENT_SERVICE_TOKEN", "super-secret")
    monkeypatch.setattr(antigravity, "run_process", fake_run_process)
    run(AntigravityRunner(workspace=tmp_path).run(make_request()))

    child_env = captured["env"]
    assert "AGENT_SERVICE_TOKEN" not in child_env
    assert captured["inherit_environment"] is False


def test_run_parses_json_response_and_uses_elapsed_duration_when_outer_duration_invalid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.runners.antigravity as antigravity

    monkeypatch.setattr(
        antigravity,
        "run_process",
        fake_process(
            success_output(duration=float("nan"), usage={"input_tokens": 0, "output_tokens": 2})
        ),
    )

    result = run(AntigravityRunner(workspace=tmp_path).run(make_request()))

    assert result.payload == {"answer": "ok"}
    assert result.input_tokens == 0
    assert result.output_tokens == 2
    assert result.duration_seconds >= 0


def test_image_paths_are_added_as_bounded_workspace_filenames_when_opted_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image = tmp_path / "photo.jpg"
    image.write_bytes(b"image")
    captured: list[list[str]] = []

    async def fake_run_process(command: list[str], **kwargs: Any) -> ProcessResult:
        captured.append(command)
        return ProcessResult(0, success_output(), "")

    import app.runners.antigravity as antigravity

    monkeypatch.setattr(antigravity, "run_process", fake_run_process)
    run(
        AntigravityRunner(workspace=tmp_path, supports_image_input=True).run(
            make_request(image_paths=(image,))
        )
    )

    assert "photo.jpg" in captured[0][2]


def test_images_are_rejected_by_default_without_invoking_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.runners.antigravity as antigravity

    async def unexpected_process(*args: Any, **kwargs: Any) -> ProcessResult:
        raise AssertionError("process should not run")

    monkeypatch.setattr(antigravity, "run_process", unexpected_process)
    image = tmp_path / "photo.jpg"

    with pytest.raises(RunnerError) as error:
        run(AntigravityRunner(workspace=tmp_path).run(make_request(image_paths=(image,))))

    assert error.value.code == "invalid_request"
    assert error.value.safe_message == "image input is not supported"


def test_image_paths_must_be_existing_regular_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.runners.antigravity as antigravity

    async def unexpected_process(*args: Any, **kwargs: Any) -> ProcessResult:
        raise AssertionError("process should not run")

    monkeypatch.setattr(antigravity, "run_process", unexpected_process)
    missing = tmp_path / "missing.jpg"

    with pytest.raises(RunnerError, match="image path is invalid"):
        run(
            AntigravityRunner(workspace=tmp_path, supports_image_input=True).run(
                make_request(image_paths=(missing,))
            )
        )


def test_invalid_schema_is_rejected_before_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.runners.antigravity as antigravity

    async def unexpected_process(*args: Any, **kwargs: Any) -> ProcessResult:
        raise AssertionError("process should not run")

    monkeypatch.setattr(antigravity, "run_process", unexpected_process)

    with pytest.raises(RunnerError) as error:
        run(
            AntigravityRunner(workspace=tmp_path).run(
                make_request(response_schema={"type": "not-a-json-schema-type"})
            )
        )

    assert error.value.code == "invalid_request"
    assert error.value.safe_message == "response schema is invalid"


def test_non_serializable_payload_is_a_safe_request_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.runners.antigravity as antigravity

    async def unexpected_process(*args: Any, **kwargs: Any) -> ProcessResult:
        raise AssertionError("process should not run")

    monkeypatch.setattr(antigravity, "run_process", unexpected_process)
    request = RunnerRequest(
        model_id="gemini-test",
        system_prompt="Return JSON.",
        input_payload={"bad": object()},
        response_schema={"type": "object"},
        schema_name="answer",
        temperature=0,
        max_output_tokens=10,
        timeout_seconds=1,
    )

    with pytest.raises(RunnerError) as error:
        run(AntigravityRunner(workspace=tmp_path).run(request))

    assert error.value.code == "invalid_request"
    assert error.value.safe_message == "request could not be prepared"
    assert "object at" not in str(error.value)


def test_schema_write_failure_cleans_up_partial_schema_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_dump(*args: Any, **kwargs: Any) -> None:
        raise TypeError("serialization failed")

    monkeypatch.setattr(json, "dump", fail_dump)

    with pytest.raises(RunnerError) as error:
        run(AntigravityRunner(workspace=tmp_path).run(make_request()))

    assert error.value.code == "invalid_request"
    assert list(tmp_path.glob(".fitsho-schema-*.json")) == []


@pytest.mark.parametrize(
    ("stdout", "code"),
    [
        ("not json", "invalid_output"),
        (json.dumps({"status": "SUCCESS", "response": "not json"}), "invalid_output"),
        (json.dumps({"status": "SUCCESS", "structured_output": ["bad"]}), "invalid_output"),
        (json.dumps({"status": "SUCCESS", "structured_output": {"wrong": True}}), "invalid_output"),
    ],
)
def test_malformed_or_schema_invalid_output_is_safe_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stdout: str, code: str
) -> None:
    import app.runners.antigravity as antigravity

    monkeypatch.setattr(antigravity, "run_process", fake_process(stdout))

    with pytest.raises(RunnerError) as error:
        run(AntigravityRunner(workspace=tmp_path).run(make_request()))

    assert error.value.code == code
    assert error.value.safe_message in {"invalid runner output", "response did not match schema"}
    assert "not json" not in str(error.value)


@pytest.mark.parametrize(
    ("status_text", "code"),
    [
        ("model not found", "model_not_found"),
        ("unauthorized: please login", "unauthorized"),
        ("temporary upstream outage", "provider_unavailable"),
        ("rate limit exceeded", "rate_limited"),
    ],
)
def test_error_status_is_classified_without_leaking_provider_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status_text: str,
    code: str,
) -> None:
    import app.runners.antigravity as antigravity

    monkeypatch.setattr(
        antigravity,
        "run_process",
        fake_process(json.dumps({"status": "ERROR", "message": status_text})),
    )

    with pytest.raises(RunnerError) as error:
        run(AntigravityRunner(workspace=tmp_path).run(make_request()))

    assert error.value.code == code
    assert error.value.safe_message in {
        "model was not found",
        "runner authorization failed",
        "runner rate limit reached",
        "provider is unavailable",
    }
    assert status_text not in str(error.value)


def test_nonzero_process_is_provider_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.runners.antigravity as antigravity

    monkeypatch.setattr(antigravity, "run_process", fake_process("", returncode=2, stderr="secret"))

    with pytest.raises(RunnerError) as error:
        run(AntigravityRunner(workspace=tmp_path).run(make_request()))

    assert error.value.code == "provider_unavailable"
    assert "secret" not in str(error.value)


def test_timeout_maps_to_safe_timeout_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.runners.antigravity as antigravity

    async def timeout_process(*args: Any, **kwargs: Any) -> ProcessResult:
        raise ProcessTimeoutError("secret process details")

    monkeypatch.setattr(antigravity, "run_process", timeout_process)

    with pytest.raises(RunnerError) as error:
        run(AntigravityRunner(workspace=tmp_path).run(make_request()))

    assert error.value.code == "timeout"
    assert error.value.safe_message == "runner timed out"
    assert "secret" not in str(error.value)
