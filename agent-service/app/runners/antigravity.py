import json
import math
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from ..process import ProcessExecutionError, ProcessTimeoutError, run_process
from ..schemas import AgentName, AuthState, RunnerCapabilities, RunnerModelCapabilities
from .base import AgentRunner, RunnerError, RunnerRequest, RunnerResult


class AntigravityRunner(AgentRunner):
    name = AgentName.ANTIGRAVITY
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
        }
    )

    def __init__(
        self,
        workspace: Path,
        executable: str = "agy",
        *,
        configured_models: tuple[str, ...] = (),
        supports_image_input: bool = False,
    ) -> None:
        self.workspace = workspace
        self.executable = executable
        self.configured_models = configured_models
        self.supports_image_input = supports_image_input

    async def capabilities(self) -> RunnerCapabilities:
        return RunnerCapabilities(
            agent=self.name,
            installed=self._is_installed(),
            version=None,
            auth_state=AuthState.UNKNOWN,
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

    def _is_installed(self) -> bool:
        executable = Path(self.executable)
        if executable.parent != Path("."):
            try:
                return executable.is_file() and executable.stat().st_mode & 0o111 != 0
            except OSError:
                return False
        return shutil.which(self.executable) is not None

    async def run(self, request: RunnerRequest) -> RunnerResult:
        workspace = self._workspace_path()
        image_names = self._image_names(request.image_paths, workspace)
        started = time.perf_counter()
        schema_path: Path | None = None

        try:
            try:
                Draft202012Validator.check_schema(request.response_schema)
            except Exception as exc:
                raise RunnerError("invalid_request", "response schema is invalid") from exc
            prompt = self._prompt(request, image_names)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=workspace,
                prefix=".fitsho-schema-",
                suffix=".json",
                delete=False,
            ) as schema_file:
                schema_path = Path(schema_file.name)
                json.dump(request.response_schema, schema_file, ensure_ascii=False)

            command = [
                self.executable,
                "--print",
                prompt,
                "--output-format",
                "json",
                "--json-schema",
                str(schema_path),
                "--model",
                request.model_id,
                "--sandbox",
            ]
            result = await run_process(
                command,
                workspace=workspace,
                timeout_seconds=request.timeout_seconds,
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
        finally:
            if schema_path is not None:
                schema_path.unlink(missing_ok=True)

        elapsed = time.perf_counter() - started
        if result.returncode != 0:
            raise self._classified_error(result.stdout, result.stderr)

        outer = self._parse_outer(result.stdout)
        if outer.get("status") == "ERROR":
            raise self._classified_error(result.stdout, result.stderr)
        if outer.get("status") != "SUCCESS":
            raise RunnerError("invalid_output", "invalid runner output")

        payload = self._parse_payload(outer)
        try:
            Draft202012Validator(request.response_schema).validate(payload)
        except Exception as exc:
            raise RunnerError("invalid_output", "response did not match schema") from exc

        usage = outer.get("usage")
        input_tokens = (
            self._nonnegative_int(usage.get("input_tokens")) if isinstance(usage, dict) else None
        )
        output_tokens = (
            self._nonnegative_int(usage.get("output_tokens")) if isinstance(usage, dict) else None
        )
        duration = outer.get("duration_seconds")
        if self._finite_nonnegative_number(duration):
            duration_seconds = float(cast(int | float, duration))
        else:
            duration_seconds = elapsed
        return RunnerResult(
            payload=payload,
            model_id=request.model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_seconds=float(duration_seconds),
        )

    def _workspace_path(self) -> Path:
        try:
            workspace = self.workspace.resolve(strict=True)
        except OSError as exc:
            raise RunnerError("invalid_request", "workspace is invalid") from exc
        if not workspace.is_dir():
            raise RunnerError("invalid_request", "workspace is invalid")
        return workspace

    @classmethod
    def _subprocess_environment(cls) -> dict[str, str]:
        return {
            key: value
            for key, value in os.environ.items()
            if key in cls._SAFE_ENVIRONMENT_KEYS
        }

    def _image_names(self, image_paths: tuple[Path, ...], workspace: Path) -> list[str]:
        if image_paths and not self.supports_image_input:
            raise RunnerError("invalid_request", "image input is not supported")
        if len(image_paths) > 5:
            raise RunnerError("invalid_request", "too many images")
        names: list[str] = []
        for image_path in image_paths:
            candidate = image_path if image_path.is_absolute() else workspace / image_path
            try:
                resolved = candidate.resolve(strict=True)
                resolved.relative_to(workspace)
            except (OSError, ValueError) as exc:
                raise RunnerError("invalid_request", "image path is invalid") from exc
            if not resolved.is_file():
                raise RunnerError("invalid_request", "image path is invalid")
            names.append(resolved.name)
        return names

    @staticmethod
    def _prompt(request: RunnerRequest, image_names: list[str]) -> str:
        prompt = (
            f"{request.system_prompt}\n\n"
            "Input JSON:\n"
            f"{json.dumps(request.input_payload, ensure_ascii=False, sort_keys=True)}\n\n"
            "Return one JSON object matching the supplied schema."
        )
        if image_names:
            prompt += "\n\nWorkspace image filenames:\n" + "\n".join(
                f"- {name[:256]}" for name in image_names
            )
        return prompt

    @staticmethod
    def _parse_outer(stdout: str) -> dict[str, Any]:
        try:
            outer = json.loads(stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            raise RunnerError("invalid_output", "invalid runner output") from exc
        if not isinstance(outer, dict):
            raise RunnerError("invalid_output", "invalid runner output")
        return outer

    @classmethod
    def _parse_payload(cls, outer: dict[str, Any]) -> dict[str, Any]:
        if "structured_output" in outer:
            payload = outer["structured_output"]
        else:
            response = outer.get("response")
            if isinstance(response, dict):
                payload = response
            elif isinstance(response, str):
                try:
                    payload = json.loads(response)
                except json.JSONDecodeError as exc:
                    raise RunnerError("invalid_output", "invalid runner output") from exc
            else:
                raise RunnerError("invalid_output", "invalid runner output")
        if not isinstance(payload, dict):
            raise RunnerError("invalid_output", "invalid runner output")
        return payload

    @classmethod
    def _classified_error(cls, stdout: str, stderr: str) -> RunnerError:
        text = " ".join((stdout, stderr)).lower()
        if re.search(r"model[ _-]+not[ _-]+found|unknown model|model does not exist", text):
            return RunnerError("model_not_found", "model was not found")
        if re.search(r"rate[ -]?limit|too many requests|quota exceeded|\b429\b", text):
            return RunnerError("rate_limited", "runner rate limit reached")
        if re.search(
            r"unauthori[sz]ed|authentication failed|not authenticated|login required|"
            r"permission denied|access denied|forbidden",
            text,
        ):
            return RunnerError("unauthorized", "runner authorization failed")
        return RunnerError("provider_unavailable", "provider is unavailable")

    @staticmethod
    def _nonnegative_int(value: Any) -> int | None:
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        return None

    @staticmethod
    def _finite_nonnegative_number(value: Any) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and value >= 0
        )
