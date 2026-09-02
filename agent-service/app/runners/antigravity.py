import json
import math
import os
import re
import shutil
import tempfile
import time
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from ..process import ProcessExecutionError, ProcessTimeoutError, run_process
from ..profiles import (
    AgentModelProfile,
    antigravity_profiles_from_output,
)
from ..proxy import ProxyRuntime
from ..schemas import (
    AgentName,
    AuthMode,
    AuthState,
    RunnerCapabilities,
    RunnerModelCapabilities,
)
from .base import (
    AgentRunner,
    RunnerError,
    RunnerRequest,
    RunnerResult,
    resolve_image_paths,
)
from .probes import CliMetadataProbe

_PYDANTIC_DECIMAL_PATTERN = r"^(?!^[-+.]*$)[+-]?0*\d*\.?\d*$"
_RE2_DECIMAL_PATTERN = r"^[+-]?(0*[0-9]+(\.[0-9]*)?|\.[0-9]+)$"
_AGY_CACHE_HOME = "/home/agent/.gemini/antigravity-cli/fitsho-cache"
_AGY_PLAYWRIGHT_BROWSERS_PATH = f"{_AGY_CACHE_HOME}/playwright"
_AGY_PLAYWRIGHT_DRIVER_PATH = f"{_AGY_CACHE_HOME}/playwright-driver"
_AGY_LOG_ROOT = Path("/home/agent/.gemini/antigravity-cli/log")


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
            "PLAYWRIGHT_BROWSERS_PATH",
            "PLAYWRIGHT_DRIVER_PATH",
        }
    )

    def __init__(
        self,
        workspace: Path,
        executable: str = "agy",
        *,
        configured_models: tuple[str, ...] = (),
        supports_image_input: bool = False,
        shared_media_root: Path = Path("/shared-private-media"),
        proxy_runtime: ProxyRuntime | None = None,
        log_root: Path = _AGY_LOG_ROOT,
    ) -> None:
        self.workspace = workspace
        self.executable = executable
        self.configured_models = configured_models
        self.supports_image_input = supports_image_input
        self.shared_media_root = shared_media_root
        self.proxy_runtime = proxy_runtime or ProxyRuntime()
        self.log_root = log_root
        self._profiles_cache: tuple[AgentModelProfile, ...] = ()
        self._profiles_cached_at = 0.0
        self._metadata = CliMetadataProbe(
            executable=self.executable,
            workspace=self.workspace,
            environment=self._subprocess_environment,
        )

    async def capabilities(self) -> RunnerCapabilities:
        installed = self._is_installed()
        version = await self._metadata.version() if installed else None
        profiles = await self._profiles(version) if installed else ()
        return RunnerCapabilities(
            agent=self.name,
            installed=installed,
            version=version,
            auth_state=AuthState.UNKNOWN,
            auth_mode=AuthMode.BROWSER_LINK,
            models=[
                RunnerModelCapabilities(
                    model_id=profile.model_id,
                    supports_text_input=True,
                    supports_image_input=self.supports_image_input,
                    supports_structured_output=True,
                    supports_live_web=True,
                )
                for profile in profiles
            ],
            profiles=list(profiles),
        )

    async def _profiles(self, version: str | None) -> tuple[AgentModelProfile, ...]:
        if self.configured_models:
            return tuple(
                _configured_profile(model_id, version, self.supports_image_input)
                for model_id in self.configured_models
            )
        now = time.monotonic()
        if self._profiles_cache and now - self._profiles_cached_at < 60.0:
            return self._profiles_cache
        try:
            result = await run_process(
                [self.executable, "models"],
                workspace=self._workspace_path(),
                timeout_seconds=15,
                env=self._subprocess_environment(),
                inherit_environment=False,
            )
        except (ProcessExecutionError, ProcessTimeoutError, OSError, ValueError):
            return self._profiles_cache
        if result.returncode != 0:
            return self._profiles_cache
        profiles = antigravity_profiles_from_output(
            result.stdout,
            version=version,
            supports_image_input=self.supports_image_input,
        )
        if profiles:
            self._profiles_cache = profiles
            self._profiles_cached_at = now
            return profiles
        return self._profiles_cache

    async def probe_auth_state(self) -> AuthState:
        return AuthState.UNKNOWN

    def _is_installed(self) -> bool:
        executable = Path(self.executable)
        if executable.parent != Path("."):
            try:
                return executable.is_file() and executable.stat().st_mode & 0o111 != 0
            except OSError:
                return False
        return shutil.which(self.executable) is not None

    async def run(self, request: RunnerRequest) -> RunnerResult:
        if request.effort is not None and request.effort not in {
            "low",
            "medium",
            "high",
            "thinking",
        }:
            raise RunnerError("invalid_request", "reasoning effort is invalid")
        if request.web_access not in {"disabled", "live"}:
            raise RunnerError("invalid_request", "web access policy is invalid")
        workspace = self._workspace_path()
        image_paths = self._image_paths(request.image_paths, workspace)
        started = time.perf_counter()
        schema_path: Path | None = None

        try:
            try:
                Draft202012Validator.check_schema(request.response_schema)
            except Exception as exc:
                raise RunnerError("invalid_request", "response schema is invalid") from exc
            prompt = self._prompt(request, image_paths)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=workspace,
                prefix=".fitsho-schema-",
                suffix=".json",
                delete=False,
            ) as schema_file:
                schema_path = Path(schema_file.name)
                json.dump(
                    _agy_compatible_schema(request.response_schema),
                    schema_file,
                    ensure_ascii=False,
                )

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
            ]
            if request.effort is not None:
                effort = "high" if request.effort == "thinking" else request.effort
                command.extend(["--effort", effort])
            # Keep the CLI in its workspace sandbox while allowing headless
            # image inspection and web tools to run without an interactive
            # permission prompt. The subprocess environment is separately
            # restricted to the safe allow-list above.
            command.extend(["--sandbox", "--dangerously-skip-permissions"])
            log_snapshot = self._cli_log_snapshot()
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
        cli_diagnostics = self._cli_log_diagnostics(log_snapshot)
        if result.returncode != 0:
            raise self._classified_error(result.stdout, f"{result.stderr}\n{cli_diagnostics}")

        outer = self._parse_outer(result.stdout)
        if outer.get("status") == "ERROR":
            raise self._classified_error(result.stdout, f"{result.stderr}\n{cli_diagnostics}")
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

    def _subprocess_environment(self) -> dict[str, str]:
        environment = {
            key: value for key, value in os.environ.items() if key in self._SAFE_ENVIRONMENT_KEYS
        }
        # /tmp is mounted noexec and the compose volume can leave the default
        # cache root-owned. Keep browser and embedded-tool caches on the
        # writable Agent Service volume where executables can run.
        environment["XDG_CACHE_HOME"] = _AGY_CACHE_HOME
        environment["PLAYWRIGHT_BROWSERS_PATH"] = _AGY_PLAYWRIGHT_BROWSERS_PATH
        environment["PLAYWRIGHT_DRIVER_PATH"] = _AGY_PLAYWRIGHT_DRIVER_PATH
        return self.proxy_runtime.apply(environment)

    def _cli_log_snapshot(self) -> dict[Path, tuple[int, int]]:
        try:
            return {
                path: (path.stat().st_mtime_ns, path.stat().st_size)
                for path in self.log_root.glob("*.log")
                if path.is_file()
            }
        except OSError:
            return {}

    def _cli_log_diagnostics(self, snapshot: dict[Path, tuple[int, int]]) -> str:
        changed_logs: list[tuple[int, Path]] = []
        try:
            for path in self.log_root.glob("*.log"):
                try:
                    stat = path.stat()
                except OSError:
                    continue
                previous = snapshot.get(path)
                current = (stat.st_mtime_ns, stat.st_size)
                if previous is None or previous != current:
                    changed_logs.append((stat.st_mtime_ns, path))
        except OSError:
            return ""

        diagnostics: list[str] = []
        for _, path in sorted(changed_logs, key=lambda item: item[0], reverse=True)[:3]:
            try:
                diagnostics.append(path.read_bytes()[-65_536:].decode(errors="replace"))
            except OSError:
                continue
        return "\n".join(diagnostics)

    def _image_paths(self, image_paths: tuple[Path, ...], workspace: Path) -> list[Path]:
        return resolve_image_paths(
            image_paths,
            workspace=workspace,
            shared_media_root=self.shared_media_root,
            supports_image_input=self.supports_image_input,
        )

    @staticmethod
    def _prompt(request: RunnerRequest, image_paths: list[Path]) -> str:
        prompt = (
            f"{request.system_prompt}\n\n"
            "Input JSON:\n"
            f"{json.dumps(request.input_payload, ensure_ascii=False, sort_keys=True)}\n\n"
            "Return one JSON object matching the supplied schema. "
            "Do not inspect or modify unrelated files. "
            "You may read only the explicitly listed image files for this request."
        )
        if image_paths:
            prompt += "\n\nImage files available for this request:\n" + "\n".join(
                f"- {path}" for path in image_paths
            )
        if request.web_access == "live":
            prompt += (
                "\n\nlive web research is required for this request. "
                "Use the browser/web tools available to this runner. "
                "Do not answer from model memory; return only evidence observed during this request."
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
        if re.search(r"rate[ -]?limit|usage limit|too many requests|quota exceeded|\b429\b", text):
            return RunnerError("rate_limited", "runner rate limit reached")
        if re.search(
            r"user location is not supported|location is not supported for the api",
            text,
        ):
            return RunnerError(
                "location_unsupported",
                "this provider does not support the current location",
            )
        if re.search(
            r"unauthori[sz]ed|authentication failed|authentication required|"
            r"not authenticated|not logged in|login required|permission denied|"
            r"access denied|forbidden",
            text,
        ):
            return RunnerError("unauthorized", "runner authorization failed")
        if re.search(
            r"invalid[ _-]?argument|invalid request|invalid schema|schema.*invalid|"
            r"invalid.*regex|missing field.*schema",
            text,
        ):
            return RunnerError("invalid_request", "request could not be prepared")
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


def _configured_profile(
    model_id: str, version: str | None, supports_image_input: bool
) -> AgentModelProfile:
    # Configured IDs are still parsed through the same stable profile boundary.
    from ..profiles import _effort_from_model_id, _profile

    return _profile(
        agent=AgentName.ANTIGRAVITY,
        model_id=model_id,
        display_name=model_id,
        effort=_effort_from_model_id(model_id),
        version=version,
        supports_image_input=supports_image_input,
    )


def _agy_compatible_schema(response_schema: dict[str, Any]) -> dict[str, Any]:
    compatible_schema = deepcopy(response_schema)
    _rewrite_unsupported_patterns(compatible_schema)
    return compatible_schema


def _rewrite_unsupported_patterns(value: Any) -> None:
    if isinstance(value, dict):
        if value.get("pattern") == _PYDANTIC_DECIMAL_PATTERN:
            value["pattern"] = _RE2_DECIMAL_PATTERN
        for child in value.values():
            _rewrite_unsupported_patterns(child)
    elif isinstance(value, list):
        for child in value:
            _rewrite_unsupported_patterns(child)
