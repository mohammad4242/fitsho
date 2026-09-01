import asyncio
import json
import os
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

import pytest

from app.process import ProcessResult, ProcessTimeoutError
from app.runners.base import RunnerError, RunnerRequest
from app.runners.codex import CodexRunner
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
        model_id="gpt-5-codex",
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
    stdout: str = "", *, returncode: int = 0, stderr: str = "", output: dict[str, Any] | None = None
) -> Callable[..., Coroutine[Any, Any, ProcessResult]]:
    async def runner(command: list[str], **kwargs: Any) -> ProcessResult:
        if output is not None:
            output_path = Path(command[command.index("--output-last-message") + 1])
            output_path.write_text(json.dumps(output), encoding="utf-8")
        return ProcessResult(returncode=returncode, stdout=stdout, stderr=stderr)

    return runner


def test_capabilities_are_text_only_by_default(tmp_path: Path) -> None:
    executable = tmp_path / "codex"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(executable.stat().st_mode | os.X_OK)

    capabilities = run(
        CodexRunner(
            workspace=tmp_path,
            executable=str(executable),
            configured_models=("gpt-5-codex",),
        ).capabilities()
    )

    assert capabilities.agent is AgentName.CODEX
    assert capabilities.installed is True
    assert capabilities.models[0].supports_text_input is True
    assert capabilities.models[0].supports_image_input is False
    assert capabilities.models[0].supports_structured_output is True


def test_run_uses_exact_safe_codex_contract_and_schema_output_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[list[str], dict[str, Any]]] = []

    async def fake_run_process(command: list[str], **kwargs: Any) -> ProcessResult:
        calls.append((command, kwargs))
        schema_path = Path(command[command.index("--output-schema") + 1])
        output_path = Path(command[command.index("--output-last-message") + 1])
        assert schema_path == tmp_path / "schema.json"
        assert output_path == tmp_path / "output.json"
        assert json.loads(schema_path.read_text(encoding="utf-8")) == make_request().response_schema
        output_path.write_text(json.dumps({"answer": "ok"}), encoding="utf-8")
        return ProcessResult(0, '{"type":"turn.completed"}\n', "")

    import app.runners.codex as codex

    monkeypatch.setattr(codex, "run_process", fake_run_process)
    result = run(CodexRunner(workspace=tmp_path).run(make_request()))

    assert result.payload == {"answer": "ok"}
    assert result.model_id == "gpt-5-codex"
    assert result.input_tokens is None
    assert result.output_tokens is None
    command, kwargs = calls[0]
    assert command == [
        "codex",
        "exec",
        "-C",
        str(tmp_path),
        "--skip-git-repo-check",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--output-schema",
        str(tmp_path / "schema.json"),
        "--output-last-message",
        str(tmp_path / "output.json"),
        "--json",
        "-m",
        "gpt-5-codex",
        "-",
    ]
    assert kwargs["workspace"] == tmp_path
    assert kwargs["input_text"].startswith("Return a concise answer.")
    assert kwargs["timeout_seconds"] == 4
    assert kwargs["inherit_environment"] is False
    assert "shell" not in kwargs
    assert "--dangerously-bypass-approvals-and-sandbox" not in command


def test_high_effort_profile_uses_codex_reasoning_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    async def fake_run_process(command: list[str], **kwargs: Any) -> ProcessResult:
        del kwargs
        calls.append(command)
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text('{"answer":"ok"}', encoding="utf-8")
        return ProcessResult(0, "", "")

    import app.runners.codex as codex

    monkeypatch.setattr(codex, "run_process", fake_run_process)
    run(CodexRunner(workspace=tmp_path).run(make_request(effort="high")))

    assert '-c' in calls[0]
    assert 'model_reasoning_effort="high"' in calls[0]


def test_jsonl_fallback_parses_message_and_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.runners.codex as codex

    stdout = "\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "private"}),
            json.dumps(
                {
                    "type": "item.completed",
                    "item": {"type": "agent_message", "text": '{"answer":"ok"}'},
                }
            ),
            json.dumps(
                {"type": "turn.completed", "usage": {"input_tokens": 12, "output_tokens": 4}}
            ),
        ]
    )
    monkeypatch.setattr(codex, "run_process", fake_process(stdout))

    result = run(CodexRunner(workspace=tmp_path).run(make_request()))

    assert result.payload == {"answer": "ok"}
    assert result.input_tokens == 12
    assert result.output_tokens == 4


def test_image_flag_is_constructed_only_when_explicitly_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image = tmp_path / "photo.jpg"
    image.write_bytes(b"image")
    commands: list[list[str]] = []

    async def fake_run_process(command: list[str], **kwargs: Any) -> ProcessResult:
        commands.append(command)
        Path(command[command.index("--output-last-message") + 1]).write_text(
            '{"answer":"seen"}', encoding="utf-8"
        )
        return ProcessResult(0, "", "")

    import app.runners.codex as codex

    monkeypatch.setattr(codex, "run_process", fake_run_process)
    result = run(
        CodexRunner(workspace=tmp_path, supports_image_input=True).run(
            make_request(image_paths=(image,))
        )
    )

    assert result.payload == {"answer": "seen"}
    assert commands[0][-3:] == ["--image", str(image), "-"]


def test_images_are_rejected_without_process_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.runners.codex as codex

    async def unexpected_process(*args: Any, **kwargs: Any) -> ProcessResult:
        raise AssertionError("process should not run")

    monkeypatch.setattr(codex, "run_process", unexpected_process)
    with pytest.raises(RunnerError, match="image input is not supported") as error:
        run(CodexRunner(workspace=tmp_path).run(make_request(image_paths=(Path("photo.jpg"),))))
    assert error.value.code == "invalid_request"


@pytest.mark.parametrize(
    ("stdout", "stderr", "returncode", "code"),
    [
        ("", "model not found", 1, "model_not_found"),
        ("", "unauthorized: login required", 1, "unauthorized"),
        ("", "rate limit exceeded", 1, "rate_limited"),
        ("", "You've hit your usage limit", 1, "rate_limited"),
        ("", "upstream unavailable", 1, "provider_unavailable"),
    ],
)
def test_provider_errors_are_classified_without_leaking_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stdout: str,
    stderr: str,
    returncode: int,
    code: str,
) -> None:
    import app.runners.codex as codex

    monkeypatch.setattr(
        codex, "run_process", fake_process(stdout, stderr=stderr, returncode=returncode)
    )
    with pytest.raises(RunnerError) as error:
        run(CodexRunner(workspace=tmp_path).run(make_request()))
    assert error.value.code == code
    assert stderr not in str(error.value)


def test_timeout_maps_to_safe_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.runners.codex as codex

    async def timeout_process(*args: Any, **kwargs: Any) -> ProcessResult:
        raise ProcessTimeoutError("private timeout details")

    monkeypatch.setattr(codex, "run_process", timeout_process)
    with pytest.raises(RunnerError) as error:
        run(CodexRunner(workspace=tmp_path).run(make_request()))
    assert error.value.code == "timeout"
    assert error.value.safe_message == "runner timed out"


@pytest.mark.parametrize("output", ["not json", json.dumps({"wrong": True}), json.dumps(["bad"])])
def test_malformed_or_schema_invalid_output_is_safe_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, output: str
) -> None:
    import app.runners.codex as codex

    async def malformed_process(command: list[str], **kwargs: Any) -> ProcessResult:
        Path(command[command.index("--output-last-message") + 1]).write_text(
            output, encoding="utf-8"
        )
        return ProcessResult(0, "not-jsonl", "")

    monkeypatch.setattr(codex, "run_process", malformed_process)
    with pytest.raises(RunnerError) as error:
        run(CodexRunner(workspace=tmp_path).run(make_request()))
    assert error.value.code == "invalid_output"
    assert "not json" not in str(error.value)


def test_invalid_schema_is_rejected_before_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.runners.codex as codex

    async def unexpected_process(*args: Any, **kwargs: Any) -> ProcessResult:
        raise AssertionError("process should not run")

    monkeypatch.setattr(codex, "run_process", unexpected_process)
    with pytest.raises(RunnerError) as error:
        run(
            CodexRunner(workspace=tmp_path).run(
                make_request(response_schema={"type": "not-a-json-schema-type"})
            )
        )
    assert error.value.code == "invalid_request"
    assert error.value.safe_message == "response schema is invalid"
