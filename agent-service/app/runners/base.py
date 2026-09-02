from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from ..schemas import AgentName, RunnerCapabilities


class RunnerError(RuntimeError):
    """A runner failure with a stable code and safe user-facing message."""

    def __init__(self, code: str, safe_message: str) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


def resolve_image_paths(
    image_paths: tuple[Path, ...],
    *,
    workspace: Path,
    shared_media_root: Path,
    supports_image_input: bool,
    max_images: int = 5,
) -> list[Path]:
    if image_paths and not supports_image_input:
        raise RunnerError("invalid_request", "image input is not supported")
    if len(image_paths) > max_images:
        raise RunnerError("invalid_request", "too many images")
    try:
        workspace_root = workspace.resolve(strict=True)
        if not workspace_root.is_dir():
            raise OSError("workspace is not a directory")
    except (OSError, RuntimeError, ValueError) as exc:
        raise RunnerError("invalid_request", "workspace is invalid") from exc
    shared_root: Path | None
    try:
        shared_root = shared_media_root.resolve(strict=True)
        if not shared_root.is_dir():
            shared_root = None
    except (OSError, RuntimeError, ValueError):
        shared_root = None

    resolved_paths: list[Path] = []
    for image_path in image_paths:
        candidate = image_path if image_path.is_absolute() else workspace_root / image_path
        try:
            resolved = candidate.resolve(strict=True)
            in_workspace = resolved.is_relative_to(workspace_root)
            in_shared_media = shared_root is not None and resolved.is_relative_to(shared_root)
        except (OSError, RuntimeError, ValueError) as exc:
            raise RunnerError("invalid_request", "image path is invalid") from exc
        if not resolved.is_file() or not (in_workspace or in_shared_media):
            raise RunnerError("invalid_request", "image path is invalid")
        resolved_paths.append(resolved)
    return resolved_paths


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
    # Set only by Agent Service's allow-listed profile resolver.
    effort: str | None = None
    web_access: Literal["disabled", "live"] = "disabled"


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
