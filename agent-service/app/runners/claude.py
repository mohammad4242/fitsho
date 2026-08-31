from __future__ import annotations

import json
import math
import os
import re
import shutil
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from ..process import ProcessExecutionError, ProcessTimeoutError, run_process
from ..schemas import AgentName, AuthMode, AuthState, RunnerCapabilities, RunnerModelCapabilities
from .base import AgentRunner, RunnerError, RunnerRequest, RunnerResult
from .probes import CliMetadataProbe


class ClaudeRunner(AgentRunner):
    """Run Claude Code in its non-interactive, machine-readable mode."""

    name = AgentName.CLAUDE
    _SAFE_ENVIRONMENT_KEYS = frozenset(
        {
            "PATH",
            "HOME",
            "USER",
            "LANG",
            "LC_ALL",
            "TERM",
            "TMPDIR",
            "XDG_CONFIG_HOME",
            "XDG_DATA_HOME",
            "XDG_CACHE_HOME",
            "DBUS_SESSION_BUS_ADDRESS",
            "DISPLAY",
            "NO_PROXY",
            "no_proxy",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "http_proxy",
            "https_proxy",
            "SSL_CERT_FILE",
            "SSL_CERT_DIR",
            "CLAUDE_CODE_DISABLE_AUTOUPDATE",
        }
    )

    def __init__(
        self,
        workspace: Path,
        executable: str = "claude",
        *,
        configured_models: tuple[str, ...] = (),
        supports_image_input: bool = False,
    ) -> None:
        self.workspace = workspace
        self.executable = executable
        self.configured_models = configured_models
        # Claude image input is deliberately opt-in until the exact container
        # invocation is smoke-tested with a subscription login.
        self.supports_image_input = supports_image_input
        self._metadata = CliMetadataProbe(
            executable=self.executable,
            workspace=self.workspace,
            environment=self._subprocess_environment(),
            auth_status_args=("auth", "status", "--json"),
            auth_status_parser=self._parse_auth_status,
        )

    async def capabilities(self) -> RunnerCapabilities:
        installed = self._is_installed()
        return RunnerCapabilities(
            agent=self.name,
            installed=installed,
            version=await self._metadata.version() if installed else None,
            auth_state=AuthState.UNKNOWN,
            auth_mode=AuthMode.BROWSER_LINK,
            models=[
                RunnerModelCapabilities(
                    model_id=model_id,
                    supports_text_input=True,
                    supports_image_input=self.supports_image_input,
                    supports_structured_output=True,
                )
                for model_id in self.configured_models
            ],
        )

    async def probe_auth_state(self) -> AuthState:
        if not self._is_installed():
            return AuthState.UNKNOWN
        return await self._metadata.auth_state()

    def _is_installed(self) -> bool:
        executable = Path(self.executable)
        if executable.parent != Path("."):
            try:
                return executable.is_file() and executable.stat().st_mode & 0o111 != 0
            except OSError:
                return False
        return shutil.which(self.executable) is not None

    @staticmethod
    def _parse_auth_status(result: Any) -> AuthState:
        try:
            document = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError):
            return AuthState.UNKNOWN
        if not isinstance(document, dict) or not isinstance(document.get("loggedIn"), bool):
            return AuthState.UNKNOWN
        return (
            AuthState.AUTHENTICATED
            if document["loggedIn"]
            else AuthState.UNAUTHENTICATED
        )

    async def run(self, request: RunnerRequest) -> RunnerResult:
        started = time.perf_counter()
        workspace = self._workspace_path()
        try:
            self._validate_request(request)
            image_paths = self._image_paths(request.image_paths, workspace)
            try:
                Draft202012Validator.check_schema(request.response_schema)
            except Exception as exc:
                raise RunnerError("invalid_request", "response schema is invalid") from exc
            command = self._command(request, request.response_schema)
            prompt = self._prompt(request, image_paths)
            try:
                result = await run_process(
                    command,
                    workspace=workspace,
                    timeout_seconds=request.timeout_seconds,
                    input_text=prompt,
                    env=self._subprocess_environment(),
                    inherit_environment=False,
                )
            except ProcessTimeoutError as exc:
                raise RunnerError("timeout", "runner timed out") from exc
            except ProcessExecutionError as exc:
                raise RunnerError("provider_unavailable", "provider is unavailable") from exc
        except RunnerError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise RunnerError("invalid_request", "request could not be prepared") from exc

        if result.returncode != 0:
            raise self._classified_error(result.stdout, result.stderr)

        payload, usage, reported_duration = self._parse_result(result.stdout, result.stderr)
        try:
            Draft202012Validator(request.response_schema).validate(payload)
        except Exception as exc:
            raise RunnerError("invalid_output", "response did not match schema") from exc

        duration_seconds = (
            reported_duration
            if reported_duration is not None
            else time.perf_counter() - started
        )
        return RunnerResult(
            payload=payload,
            model_id=request.model_id,
            input_tokens=self._usage_int(usage, "input_tokens"),
            output_tokens=self._usage_int(usage, "output_tokens"),
            duration_seconds=float(duration_seconds),
        )

    @staticmethod
    def _workspace_path_for(workspace: Path) -> Path:
        try:
            resolved = workspace.resolve(strict=True)
        except OSError as exc:
            raise RunnerError("invalid_request", "workspace is invalid") from exc
        if not resolved.is_dir():
            raise RunnerError("invalid_request", "workspace is invalid")
        return resolved

    def _workspace_path(self) -> Path:
        return self._workspace_path_for(self.workspace)

    @staticmethod
    def _validate_request(request: RunnerRequest) -> None:
        if not isinstance(request.model_id, str) or not request.model_id.strip():
            raise RunnerError("invalid_request", "model is invalid")

    def _image_paths(self, image_paths: tuple[Path, ...], workspace: Path) -> list[Path]:
        if image_paths and not self.supports_image_input:
            raise RunnerError("invalid_request", "image input is not supported")
        if len(image_paths) > 5:
            raise RunnerError("invalid_request", "too many images")
        resolved_paths: list[Path] = []
        for image_path in image_paths:
            candidate = image_path if image_path.is_absolute() else workspace / image_path
            try:
                resolved = candidate.resolve(strict=True)
                resolved.relative_to(workspace)
            except (OSError, ValueError) as exc:
                raise RunnerError("invalid_request", "image path is invalid") from exc
            if not resolved.is_file():
                raise RunnerError("invalid_request", "image path is invalid")
            resolved_paths.append(resolved)
        return resolved_paths

    def _command(self, request: RunnerRequest, response_schema: dict[str, Any]) -> list[str]:
        try:
            serialized_schema = json.dumps(response_schema, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise RunnerError("invalid_request", "request could not be prepared") from exc
        return [
            self.executable,
            "--print",
            "--output-format",
            "json",
            "--no-session-persistence",
            "--model",
            request.model_id,
            "--permission-mode",
            "plan",
            "--json-schema",
            serialized_schema,
            "-",
        ]

    def _prompt(self, request: RunnerRequest, image_paths: Iterable[Path]) -> str:
        try:
            input_json = json.dumps(request.input_payload, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise RunnerError("invalid_request", "request could not be prepared") from exc
        prompt = (
            f"{request.system_prompt}\n\n"
            "Input JSON:\n"
            f"{input_json}\n\n"
            "Return only one JSON object matching the supplied output schema. "
            "Do not inspect or change files."
        )
        paths = tuple(image_paths)
        if paths:
            prompt += "\n\nWorkspace image filenames:\n" + "\n".join(
                f"- {path.name[:256]}" for path in paths
            )
        return prompt

    @classmethod
    def _parse_result(
        cls, stdout: str, stderr: str
    ) -> tuple[dict[str, Any], dict[str, Any], float | None]:
        try:
            document: Any = json.loads(stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            raise RunnerError("invalid_output", "invalid runner output") from exc
        if not isinstance(document, dict):
            raise RunnerError("invalid_output", "invalid runner output")
        if document.get("is_error") is True or document.get("subtype") in {
            "error",
            "error_during_execution",
        }:
            raise cls._classified_error(json.dumps(document), stderr)
        if document.get("type") in {"error", "turn.failed"}:
            raise cls._classified_error(json.dumps(document), stderr)

        usage = document.get("usage")
        if not isinstance(usage, dict):
            usage = {}
        reported_duration = cls._duration_seconds(document.get("duration_ms"))
        if reported_duration is None:
            reported_duration = cls._duration_seconds(document.get("duration_api_ms"))

        for key in ("structured_output", "response", "result", "output"):
            if key in document:
                payload = cls._object_from_value(document[key])
                if payload is None:
                    raise RunnerError("invalid_output", "invalid runner output")
                return payload, usage, reported_duration

        # A test double or future CLI may emit the structured object directly.
        if not set(document).intersection({"type", "subtype", "is_error", "usage"}):
            return document, usage, reported_duration
        raise RunnerError("invalid_output", "invalid runner output")

    @staticmethod
    def _object_from_value(value: Any) -> dict[str, Any] | None:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                nested = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return None
            return nested if isinstance(nested, dict) else None
        if isinstance(value, list):
            text = "".join(
                item.get("text", "") for item in value if isinstance(item, dict)
            )
            if not text:
                return None
            try:
                nested = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                return None
            return nested if isinstance(nested, dict) else None
        return None

    @staticmethod
    def _duration_seconds(value: Any) -> float | None:
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            and value >= 0
        ):
            return float(value) / 1000.0
        return None

    @classmethod
    def _classified_error(cls, stdout: str, stderr: str) -> RunnerError:
        text = " ".join((stdout, stderr)).lower()
        if re.search(r"model[ _-]+not[ _-]+found|unknown model|model does not exist", text):
            return RunnerError("model_not_found", "model was not found")
        if re.search(
            r"rate[ -]?limit|too many requests|quota exceeded|credit balance|\b429\b", text
        ):
            return RunnerError("rate_limited", "runner rate limit reached")
        if re.search(
            r"unauthori[sz]ed|authentication failed|not authenticated|login required|"
            r"not logged in|permission denied|access denied|forbidden|invalid api key",
            text,
        ):
            return RunnerError("unauthorized", "runner authorization failed")
        return RunnerError("provider_unavailable", "provider is unavailable")

    @staticmethod
    def _usage_int(usage: dict[str, Any], key: str) -> int | None:
        value = usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        return None

    @classmethod
    def _subprocess_environment(cls) -> dict[str, str]:
        return {
            key: value for key, value in os.environ.items() if key in cls._SAFE_ENVIRONMENT_KEYS
        }
