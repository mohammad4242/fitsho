import asyncio
import json
import os
from collections.abc import Callable, Coroutine
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from app.process import ProcessResult, ProcessTimeoutError
from app.runners.base import RunnerError, RunnerRequest
from app.runners.claude import ClaudeRunner
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
        model_id="claude-sonnet-4-20250514",
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
    stdout: str = "", *, returncode: int = 0, stderr: str = ""
) -> Callable[..., Coroutine[Any, Any, ProcessResult]]:
    async def runner(*args: Any, **kwargs: Any) -> ProcessResult:
        return ProcessResult(returncode=returncode, stdout=stdout, stderr=stderr)

    return runner


def test_capabilities_are_text_only_by_default(tmp_path: Path) -> None:
    executable = tmp_path / "claude"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(executable.stat().st_mode | os.X_OK)

    capabilities = run(
        ClaudeRunner(
            workspace=tmp_path,
            executable=str(executable),
            configured_models=("claude-sonnet-4-20250514",),
        ).capabilities()
    )

    assert capabilities.agent is AgentName.CLAUDE
    assert capabilities.installed is True
    assert capabilities.models[0].supports_text_input is True
    assert capabilities.models[0].supports_image_input is False
    assert capabilities.models[0].supports_structured_output is True


def test_run_uses_exact_claude_contract_inline_schema_and_stdin_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    async def fake_run_process(command: list[str], **kwargs: Any) -> ProcessResult:
        calls.append((command, kwargs))
        return ProcessResult(
            0,
            json.dumps(
                {
                    "type": "result",
                    "subtype": "success",
                    "result": '{"answer":"ok"}',
                    "usage": {"input_tokens": 12, "output_tokens": 4},
                }
            ),
            "",
        )

    import app.runners.claude as claude

    monkeypatch.setenv("AGENT_SERVICE_TOKEN", "super-secret")
    monkeypatch.setattr(claude, "run_process", fake_run_process)
    result = run(ClaudeRunner(workspace=tmp_path).run(make_request()))

    assert result.payload == {"answer": "ok"}
    assert result.input_tokens == 12
    assert result.output_tokens == 4
    command, kwargs = calls[0]
    assert command == [
        "claude",
        "--print",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--model",
        "claude-sonnet-4-20250514",
        "--permission-mode",
        "plan",
        "--json-schema",
        json.dumps(make_request().response_schema, ensure_ascii=False),
        "-",
    ]
    assert kwargs["input_text"].startswith("Return a concise answer.")
    assert '"question": "hello"' in kwargs["input_text"]
    assert kwargs["workspace"] == tmp_path
    assert kwargs["timeout_seconds"] == 4
    assert kwargs["inherit_environment"] is False
    assert "AGENT_SERVICE_TOKEN" not in kwargs["env"]
    assert "--dangerously-skip-permissions" not in command


def test_live_web_allows_only_claude_web_tools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    async def fake_run_process(command: list[str], **kwargs: Any) -> ProcessResult:
        calls.append((command, kwargs))
        return ProcessResult(0, '{"result":"{\\"answer\\":\\"live\\"}"}', "")

    import app.runners.claude as claude

    monkeypatch.setattr(claude, "run_process", fake_run_process)
    request = replace(make_request(), web_access="live")
    result = run(ClaudeRunner(workspace=tmp_path).run(request))

    assert result.payload == {"answer": "live"}
    command, kwargs = calls[0]
    tools_index = command.index("--allowedTools")
    assert command[tools_index + 1 : tools_index + 3] == ["WebSearch", "WebFetch"]
    assert not {"Bash", "Edit", "Write"}.intersection(command[tools_index + 1 :])
    assert "live web research" in kwargs["input_text"]


@pytest.mark.parametrize(
    "stdout",
    [
        json.dumps({"structured_output": {"answer": "ok"}}),
        json.dumps({"result": '{"answer":"ok"}'}),
        json.dumps({"response": {"answer": "ok"}}),
    ],
)
def test_run_parses_known_claude_json_output_forms(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stdout: str
) -> None:
    import app.runners.claude as claude

    monkeypatch.setattr(claude, "run_process", fake_process(stdout))
    result = run(ClaudeRunner(workspace=tmp_path).run(make_request()))

    assert result.payload == {"answer": "ok"}


@pytest.mark.parametrize(
    ("stdout", "stderr", "returncode", "code"),
    [
        ("", "model not found", 1, "model_not_found"),
        ("", "unauthorized: login required", 1, "unauthorized"),
        ("", "rate limit exceeded", 1, "rate_limited"),
        ("", "You've hit your usage limit", 1, "rate_limited"),
    ],
)
def test_provider_errors_map_to_safe_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stdout: str,
    stderr: str,
    returncode: int,
    code: str,
) -> None:
    import app.runners.claude as claude

    monkeypatch.setattr(
        claude, "run_process", fake_process(stdout, stderr=stderr, returncode=returncode)
    )
    with pytest.raises(RunnerError) as error:
        run(ClaudeRunner(workspace=tmp_path).run(make_request()))

    assert error.value.code == code
    assert stderr not in str(error.value)


def test_not_logged_in_json_result_maps_to_unauthorized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.runners.claude as claude

    stdout = json.dumps(
        {
            "is_error": True,
            "subtype": "success",
            "result": "Not logged in · Please run /login",
        }
    )
    monkeypatch.setattr(claude, "run_process", fake_process(stdout, returncode=1))

    with pytest.raises(RunnerError) as error:
        run(ClaudeRunner(workspace=tmp_path).run(make_request()))

    assert error.value.code == "unauthorized"


def test_timeout_maps_to_safe_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.runners.claude as claude

    async def timeout_process(*args: Any, **kwargs: Any) -> ProcessResult:
        raise ProcessTimeoutError("private timeout details")

    monkeypatch.setattr(claude, "run_process", timeout_process)
    with pytest.raises(RunnerError) as error:
        run(ClaudeRunner(workspace=tmp_path).run(make_request()))

    assert error.value.code == "timeout"
    assert error.value.safe_message == "runner timed out"


@pytest.mark.parametrize("stdout", ["not json", json.dumps({"result": "not-json"})])
def test_invalid_output_is_safe_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stdout: str
) -> None:
    import app.runners.claude as claude

    monkeypatch.setattr(claude, "run_process", fake_process(stdout))
    with pytest.raises(RunnerError) as error:
        run(ClaudeRunner(workspace=tmp_path).run(make_request()))

    assert error.value.code == "invalid_output"
    assert "not json" not in str(error.value)


def test_invalid_schema_is_rejected_before_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.runners.claude as claude

    async def unexpected_process(*args: Any, **kwargs: Any) -> ProcessResult:
        raise AssertionError("process should not run")

    monkeypatch.setattr(claude, "run_process", unexpected_process)
    with pytest.raises(RunnerError) as error:
        run(
            ClaudeRunner(workspace=tmp_path).run(
                make_request(response_schema={"type": "not-a-json-schema-type"})
            )
        )

    assert error.value.code == "invalid_request"
    assert error.value.safe_message == "response schema is invalid"


def test_images_are_rejected_without_process_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.runners.claude as claude

    async def unexpected_process(*args: Any, **kwargs: Any) -> ProcessResult:
        raise AssertionError("process should not run")

    monkeypatch.setattr(claude, "run_process", unexpected_process)
    with pytest.raises(RunnerError, match="image input is not supported") as error:
        run(ClaudeRunner(workspace=tmp_path).run(make_request(image_paths=(Path("photo.jpg"),))))

    assert error.value.code == "invalid_request"


def test_shared_media_image_path_is_listed_for_claude_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    shared_root = tmp_path / "shared"
    workspace.mkdir()
    image = shared_root / "food/cd/image.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"image")
    prompts: list[str] = []

    async def fake_run_process(command: list[str], **kwargs: Any) -> ProcessResult:
        prompts.append(kwargs["input_text"])
        return ProcessResult(0, '{"result":"{\\"answer\\":\\"ok\\"}"}', "")

    import app.runners.claude as claude

    monkeypatch.setattr(claude, "run_process", fake_run_process)
    result = run(
        ClaudeRunner(
            workspace=workspace,
            shared_media_root=shared_root,
            supports_image_input=True,
        ).run(make_request(image_paths=(image,)))
    )

    assert result.payload == {"answer": "ok"}
    assert f"- {image.resolve()}" in prompts[0]
    assert "Do not inspect or modify unrelated files." in prompts[0]


def test_thinking_profile_uses_claude_effort_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    async def fake_run_process(command: list[str], **kwargs: Any) -> ProcessResult:
        del kwargs
        calls.append(command)
        return ProcessResult(0, '{"result":{"answer":"ok"}}', "")

    import app.runners.claude as claude

    monkeypatch.setattr(claude, "run_process", fake_run_process)
    run(ClaudeRunner(workspace=tmp_path).run(make_request(effort="thinking")))

    assert "--effort" in calls[0]
    assert calls[0][calls[0].index("--effort") + 1] == "high"
