from pathlib import Path

from pydantic import SecretStr

from app.config import Settings
from app.runners.registry import RunnerRegistry
from app.schemas import AgentName


def test_settings_registry_registers_all_supported_runners(tmp_path: Path) -> None:
    settings = Settings(
        agent_service_token=SecretStr("t" * 32),
        agent_workspace_root=tmp_path,
        agent_antigravity_models=("gemini-test",),
        agent_codex_models=("gpt-5-codex",),
        agent_claude_models=("claude-sonnet",),
    )

    registry = RunnerRegistry.from_settings(settings)

    assert registry.get(AgentName.ANTIGRAVITY) is not None
    assert registry.get(AgentName.CODEX) is not None
    assert registry.get(AgentName.CLAUDE) is not None
