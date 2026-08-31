from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..schemas import AgentName, RunnerCapabilities


@dataclass(frozen=True)
class RunnerRequest:
    model_id: str
    system_prompt: str
    input_payload: dict[str, Any]
    response_schema: dict[str, Any]
    schema_name: str
    temperature: float
    max_output_tokens: int
    timeout_seconds: float
    image_paths: tuple[Path, ...] = ()


@dataclass(frozen=True)
class RunnerResult:
    payload: dict[str, Any]
    model_id: str
    input_tokens: int | None
    output_tokens: int | None
    duration_seconds: float


class AgentRunner(Protocol):
    name: AgentName

    async def capabilities(self) -> RunnerCapabilities: ...

    async def run(self, request: RunnerRequest) -> RunnerResult: ...
