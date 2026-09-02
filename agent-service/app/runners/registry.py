from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

from ..config import Settings
from ..proxy import ProxyRuntime
from ..schemas import AgentName, AuthState, RunnerCapabilities
from .antigravity import AntigravityRunner
from .base import AgentRunner
from .claude import ClaudeRunner
from .codex import CodexRunner


class RunnerRegistry:
    """The single boundary between HTTP routing and CLI runner implementations."""

    def __init__(
        self,
        runners: Iterable[AgentRunner],
        workspace_factories: Mapping[AgentName, Callable[[Path], AgentRunner]] | None = None,
    ) -> None:
        self._runners = {runner.name: runner for runner in runners}
        self._workspace_factories = dict(workspace_factories or {})
        self._auth_states = {runner.name: AuthState.UNKNOWN for runner in self._runners.values()}

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        proxy_runtime: ProxyRuntime | None = None,
    ) -> "RunnerRegistry":
        runtime = proxy_runtime or ProxyRuntime()
        antigravity = AntigravityRunner(
            workspace=Path(settings.agent_workspace_root),
            executable=settings.agent_antigravity_executable,
            configured_models=settings.agent_antigravity_models,
            supports_image_input=settings.agent_antigravity_supports_image_input,
            shared_media_root=Path(settings.agent_shared_private_media_root),
            proxy_runtime=runtime,
        )
        codex = CodexRunner(
            workspace=Path(settings.agent_workspace_root),
            executable=settings.agent_codex_executable,
            configured_models=settings.agent_codex_models,
            supports_image_input=settings.agent_codex_supports_image_input,
            shared_media_root=Path(settings.agent_shared_private_media_root),
            proxy_runtime=runtime,
        )
        claude = ClaudeRunner(
            workspace=Path(settings.agent_workspace_root),
            executable=settings.agent_claude_executable,
            configured_models=settings.agent_claude_models,
            supports_image_input=settings.agent_claude_supports_image_input,
            shared_media_root=Path(settings.agent_shared_private_media_root),
            proxy_runtime=runtime,
        )

        def antigravity_workspace_runner(workspace: Path) -> AgentRunner:
            return AntigravityRunner(
                workspace=workspace,
                executable=settings.agent_antigravity_executable,
                configured_models=settings.agent_antigravity_models,
                supports_image_input=settings.agent_antigravity_supports_image_input,
                shared_media_root=Path(settings.agent_shared_private_media_root),
                proxy_runtime=runtime,
            )

        def codex_workspace_runner(workspace: Path) -> AgentRunner:
            return CodexRunner(
                workspace=workspace,
                executable=settings.agent_codex_executable,
                configured_models=settings.agent_codex_models,
                supports_image_input=settings.agent_codex_supports_image_input,
                shared_media_root=Path(settings.agent_shared_private_media_root),
                proxy_runtime=runtime,
            )

        def claude_workspace_runner(workspace: Path) -> AgentRunner:
            return ClaudeRunner(
                workspace=workspace,
                executable=settings.agent_claude_executable,
                configured_models=settings.agent_claude_models,
                supports_image_input=settings.agent_claude_supports_image_input,
                shared_media_root=Path(settings.agent_shared_private_media_root),
                proxy_runtime=runtime,
            )

        return cls(
            (antigravity, codex, claude),
            {
                AgentName.ANTIGRAVITY: antigravity_workspace_runner,
                AgentName.CODEX: codex_workspace_runner,
                AgentName.CLAUDE: claude_workspace_runner,
            },
        )

    def get(self, agent: AgentName) -> AgentRunner | None:
        return self._runners.get(agent)

    def for_workspace(self, agent: AgentName, workspace: Path) -> AgentRunner | None:
        runner = self.get(agent)
        if runner is None:
            return None
        factory = self._workspace_factories.get(agent)
        return factory(workspace) if factory is not None else runner

    def set_auth_state(self, agent: AgentName, state: AuthState) -> None:
        if agent in self._runners:
            self._auth_states[agent] = state

    async def capabilities(self) -> list[RunnerCapabilities]:
        result: list[RunnerCapabilities] = []
        for runner in self._runners.values():
            try:
                capabilities = await runner.capabilities()
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
                continue
            state = self._auth_states.get(runner.name, capabilities.auth_state)
            if state is AuthState.UNKNOWN and capabilities.auth_state is not AuthState.UNKNOWN:
                state = capabilities.auth_state
            if capabilities.installed:
                probe = getattr(runner, "probe_auth_state", None)
                if probe is not None:
                    try:
                        probed_state = await probe()
                    except Exception:
                        probed_state = AuthState.UNKNOWN
                    state = probed_state
            self._auth_states[runner.name] = state
            result.append(capabilities.model_copy(update={"auth_state": state}))
        return result
