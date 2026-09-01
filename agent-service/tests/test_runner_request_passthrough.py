import json
from pathlib import Path

from app.runners.antigravity import AntigravityRunner
from app.runners.base import RunnerRequest
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
