import json
from pathlib import Path

import pytest

from app.runners.antigravity import AntigravityRunner
from app.runners.base import RunnerError, RunnerRequest, resolve_image_paths
from app.runners.claude import ClaudeRunner
from app.runners.codex import CodexRunner


def test_all_cli_runners_receive_backend_prompt_and_payload_without_task_mutation(
    tmp_path: Path,
) -> None:
    request = RunnerRequest(
        model_id="model",
        system_prompt="Fitsho canonical task marker: do not rewrite this sentence.",
        input_payload={"semantic_marker": "preserve exact value", "nested": {"number": 7}},
        response_schema={
            "type": "object",
            "properties": {"answer": {"type": "string"}},
            "required": ["answer"],
        },
        schema_name="canonical_task",
        temperature=0.4,
        max_output_tokens=321,
        timeout_seconds=9,
    )
    input_json = json.dumps(request.input_payload, ensure_ascii=False, sort_keys=True)

    prompts = (
        CodexRunner._prompt(request),
        ClaudeRunner(workspace=tmp_path)._prompt(request, ()),
        AntigravityRunner._prompt(request, []),
    )

    for prompt in prompts:
        assert prompt.startswith(request.system_prompt)
        assert f"Input JSON:\n{input_json}\n\n" in prompt


def test_runner_image_paths_allow_only_workspace_or_shared_media_root(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    shared_root = tmp_path / "shared"
    workspace.mkdir()
    shared_image = shared_root / "body/ab/image.jpg"
    shared_image.parent.mkdir(parents=True)
    shared_image.write_bytes(b"image")
    workspace_image = workspace / "workspace.jpg"
    workspace_image.write_bytes(b"image")

    assert resolve_image_paths(
        (shared_image, workspace_image),
        workspace=workspace,
        shared_media_root=shared_root,
        supports_image_input=True,
    ) == [shared_image.resolve(), workspace_image.resolve()]


@pytest.mark.parametrize("path", [Path("/etc/passwd"), Path("/home/agent/secret.jpg")])
def test_runner_image_paths_reject_arbitrary_absolute_files(tmp_path: Path, path: Path) -> None:
    workspace = tmp_path / "workspace"
    shared_root = tmp_path / "shared"
    workspace.mkdir()
    shared_root.mkdir()

    with pytest.raises(RunnerError, match="image path is invalid"):
        resolve_image_paths(
            (path,),
            workspace=workspace,
            shared_media_root=shared_root,
            supports_image_input=True,
        )
