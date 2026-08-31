import json
import os
import re
import shutil
import tempfile
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from ..process import ProcessExecutionError, ProcessTimeoutError, run_process
from ..schemas import AgentName, AuthMode, AuthState, RunnerCapabilities, RunnerModelCapabilities
from .base import AgentRunner, RunnerError, RunnerRequest, RunnerResult
from .probes import CliMetadataProbe


class CodexRunner(AgentRunner):
    """Run the pinned Codex CLI through its non-interactive JSON contract."""

    name = AgentName.CODEX
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
        executable: str = "codex",
        *,
        configured_models: tuple[str, ...] = (),
        supports_image_input: bool = False,
    ) -> None:
        self.workspace = workspace
        self.executable = executable
        self.configured_models = configured_models
        # This opt-in is deliberately false until the exact container capability is tested.
        self.supports_image_input = supports_image_input
        self._metadata = CliMetadataProbe(
            executable=self.executable,
            workspace=self.workspace,
            environment=self._subprocess_environment(),
            auth_status_args=("login", "status"),
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
        text = (result.stdout + "\n" + result.stderr).lower()
        if result.returncode == 0:
            return AuthState.AUTHENTICATED
        if "not logged in" in text or "not authenticated" in text:
            return AuthState.UNAUTHENTICATED
        return AuthState.UNKNOWN

    async def run(self, request: RunnerRequest) -> RunnerResult:
        started = time.perf_counter()
        workspace = self._workspace_path()
        schema_path = workspace / "schema.json"
        output_path = workspace / "output.json"

        try:
            self._validate_request(request)
            image_paths = self._image_paths(request.image_paths, workspace)
            try:
                Draft202012Validator.check_schema(request.response_schema)
            except Exception as exc:
                raise RunnerError("invalid_request", "response schema is invalid") from exc

            _atomic_json_write(schema_path, request.response_schema)
            output_path.unlink(missing_ok=True)
            command = self._command(request, workspace, schema_path, output_path, image_paths)
            prompt = self._prompt(request)
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

            output_text = ""
            try:
                output_text = output_path.read_text(encoding="utf-8")
            except FileNotFoundError:
                pass
            except OSError as exc:
                raise RunnerError("invalid_output", "invalid runner output") from exc
        except RunnerError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise RunnerError("invalid_request", "request could not be prepared") from exc
        finally:
            schema_path.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)

        if result.returncode != 0:
            raise self._classified_error(result.stdout, result.stderr)

        payload, usage = self._parse_result(output_text, result.stdout, result.stderr)
        try:
            Draft202012Validator(request.response_schema).validate(payload)
        except Exception as exc:
            raise RunnerError("invalid_output", "response did not match schema") from exc

        return RunnerResult(
            payload=payload,
            model_id=request.model_id,
            input_tokens=self._usage_int(usage, "input_tokens"),
            output_tokens=self._usage_int(usage, "output_tokens"),
            duration_seconds=time.perf_counter() - started,
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

    def _command(
        self,
        request: RunnerRequest,
        workspace: Path,
        schema_path: Path,
        output_path: Path,
        image_paths: Iterable[Path],
    ) -> list[str]:
        command = [
            self.executable,
            "exec",
            "-C",
            str(workspace),
            "--skip-git-repo-check",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(output_path),
            "--json",
            "-m",
            request.model_id,
        ]
        for image_path in image_paths:
            command.extend(["--image", str(image_path)])
        command.append("-")
        return command

    @staticmethod
    def _prompt(request: RunnerRequest) -> str:
        try:
            input_json = json.dumps(request.input_payload, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise RunnerError("invalid_request", "request could not be prepared") from exc
        return (
            f"{request.system_prompt}\n\n"
            "Input JSON:\n"
            f"{input_json}\n\n"
            "Return only one JSON object matching the supplied output schema. "
            "Do not inspect or change files."
        )

    @classmethod
    def _parse_result(
        cls, output_text: str, stdout: str, stderr: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if output_text.strip():
            try:
                payload, output_usage = cls._parse_document(output_text)
                return payload, output_usage
            except RunnerError:
                # A partially written output file can accompany a valid JSONL event stream.
                pass

        events: list[dict[str, Any]] = []
        for line in stdout.splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, TypeError) as exc:
                raise RunnerError("invalid_output", "invalid runner output") from exc
            if not isinstance(event, dict):
                raise RunnerError("invalid_output", "invalid runner output")
            events.append(event)

        for event in events:
            if event.get("status") == "ERROR" or event.get("type") in {"error", "turn.failed"}:
                raise cls._classified_error(json.dumps(event), stderr)

        usage: dict[str, Any] = {}
        for event in events:
            candidate_usage = event.get("usage")
            if isinstance(candidate_usage, dict):
                usage.update(candidate_usage)

        for event in reversed(events):
            candidate = cls._event_payload(event)
            if candidate is not None:
                return candidate, usage
        raise RunnerError("invalid_output", "invalid runner output")

    @classmethod
    def _parse_document(cls, text: str) -> tuple[dict[str, Any], dict[str, Any]]:
        try:
            document: Any = json.loads(text)
        except (json.JSONDecodeError, TypeError) as exc:
            raise RunnerError("invalid_output", "invalid runner output") from exc
        if not isinstance(document, dict):
            raise RunnerError("invalid_output", "invalid runner output")
        usage = document.get("usage", {}) if isinstance(document, dict) else {}
        if not isinstance(usage, dict):
            usage = {}
        if isinstance(document, dict) and document.get("status") == "ERROR":
            raise cls._classified_error(json.dumps(document), "")
        payload = cls._event_payload(document)
        if payload is None:
            raise RunnerError("invalid_output", "invalid runner output")
        return payload, usage

    @classmethod
    def _event_payload(cls, event: dict[str, Any]) -> dict[str, Any] | None:
        for key in ("structured_output", "response", "output"):
            if key in event:
                return cls._object_from_value(event[key])

        item = event.get("item")
        if isinstance(item, dict):
            payload = cls._event_payload(item)
            if payload is not None:
                return payload

        event_type = event.get("type")
        if event_type in {"agent_message", "assistant", "message"}:
            for key in ("text", "content"):
                if key in event:
                    return cls._object_from_value(event[key])

        metadata_keys = {"type", "status", "usage", "thread_id", "turn_id", "item"}
        if not set(event).intersection(metadata_keys - {"type"}):
            return event
        return None

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
            text_parts = [item.get("text", "") for item in value if isinstance(item, dict)]
            if text_parts:
                try:
                    nested = json.loads("".join(text_parts))
                except (json.JSONDecodeError, TypeError):
                    return None
                return nested if isinstance(nested, dict) else None
        return None

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

    @classmethod
    def _usage_int(cls, usage: dict[str, Any], key: str) -> int | None:
        value = usage.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
        return None

    @classmethod
    def _subprocess_environment(cls) -> dict[str, str]:
        return {
            key: value for key, value in os.environ.items() if key in cls._SAFE_ENVIRONMENT_KEYS
        }


def _atomic_json_write(path: Path, payload: object) -> None:
    try:
        serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    except (TypeError, ValueError) as exc:
        raise RunnerError("invalid_request", "request could not be prepared") from exc

    staged: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}-",
            suffix=".tmp",
            delete=False,
        ) as file:
            staged = Path(file.name)
            file.write(serialized)
            file.flush()
            os.fsync(file.fileno())
        os.replace(staged, path)
    except OSError as exc:
        raise RunnerError("invalid_request", "request could not be prepared") from exc
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
