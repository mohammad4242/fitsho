from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

from ..config import Settings
from ..schemas import AgentName, AuthState, RunnerCapabilities
from .antigravity import AntigravityRunner
from .base import AgentRunner


class RunnerRegistry:
    """The single boundary between HTTP routing and CLI runner implementations."""

    def __init__(
        self,
        runners: Iterable[AgentRunner],
        workspace_factories: Mapping[AgentName, Callable[[Path], AgentRunner]] | None = None,
    ) -> None:
        self._runners = {runner.name: runner for runner in runners}
        self._workspace_factories = dict(workspace_factories or {})

    @classmethod
    def from_settings(cls, settings: Settings) -> "RunnerRegistry":
        runner = AntigravityRunner(
            workspace=Path(settings.agent_workspace_root),
            executable=settings.agent_antigravity_executable,
            configured_models=settings.agent_antigravity_models,
            supports_image_input=settings.agent_antigravity_supports_image_input,
        )
        executable = settings.agent_antigravity_executable
        configured_models = settings.agent_antigravity_models
        supports_image_input = settings.agent_antigravity_supports_image_input

        def workspace_runner(workspace: Path) -> AgentRunner:
            return AntigravityRunner(
                workspace=workspace,
                executable=executable,
                configured_models=configured_models,
                supports_image_input=supports_image_input,
            )

        return cls((runner,), {AgentName.ANTIGRAVITY: workspace_runner})

    def get(self, agent: AgentName) -> AgentRunner | None:
        return self._runners.get(agent)

    def for_workspace(self, agent: AgentName, workspace: Path) -> AgentRunner | None:
        runner = self.get(agent)
        if runner is None:
            return None
        factory = self._workspace_factories.get(agent)
        return factory(workspace) if factory is not None else runner

    async def capabilities(self) -> list[RunnerCapabilities]:
        result: list[RunnerCapabilities] = []
        for runner in self._runners.values():
            try:
                result.append(await runner.capabilities())
            except Exception:
                result.append(
                    RunnerCapabilities(
                        agent=runner.name,
                        installed=False,
                        version=None,
                        auth_state=AuthState.UNKNOWN,
                        models=[],
                    )
                )
        return result
