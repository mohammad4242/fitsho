from collections.abc import Sequence
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from jsonschema.exceptions import SchemaError  # type: ignore[import-untyped]
from PIL import Image, UnidentifiedImageError

from .concurrency import ConcurrencyController, ConcurrencyLimitError
from .errors import AgentServiceError
from .profiles import AgentModelProfile, ResolvedProfile, legacy_profile
from .runners.base import AgentRunner, RunnerError, RunnerRequest, RunnerResult
from .runners.registry import RunnerRegistry
from .schemas import (
    AgentGenerationInput,
    AgentGenerationOutput,
    AgentName,
    AuthState,
    ErrorCode,
    RunnerCapabilities,
    TestOutput,
    TestRequest,
)
from .workspace import RequestWorkspace, WorkspaceLimits

_TEST_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"ok": {"const": True}},
    "required": ["ok"],
    "additionalProperties": True,
}

_RUNNER_STATUS: dict[str, tuple[ErrorCode, int]] = {
    "timeout": (ErrorCode.TIMEOUT, 504),
    "unauthorized": (ErrorCode.UNAUTHORIZED, 401),
    "rate_limited": (ErrorCode.RATE_LIMITED, 429),
    "invalid_request": (ErrorCode.INVALID_REQUEST, 422),
    "invalid_output": (ErrorCode.INVALID_OUTPUT, 502),
    "model_not_found": (ErrorCode.MODEL_NOT_FOUND, 404),
    "provider_unavailable": (ErrorCode.PROVIDER_UNAVAILABLE, 503),
}

_IMAGE_FORMATS = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
}


class AgentService:
    def __init__(
        self,
        registry: RunnerRegistry,
        concurrency: ConcurrencyController,
        workspace_root: Path,
        workspace_limits: WorkspaceLimits,
    ) -> None:
        self.registry = registry
        self.concurrency = concurrency
        self.workspace_root = workspace_root
        self.workspace_limits = workspace_limits

    async def capabilities(self) -> list[RunnerCapabilities]:
        return await self.registry.capabilities()

    async def test(self, request: TestRequest, request_id: str) -> TestOutput:
        runner = self._runner(request.agent)
        resolved = await self._resolve_profile(
            runner,
            request.agent,
            profile_id=request.profile_id,
            model_id=request.model_id,
        )
        await self._check_capability(resolved.profile, request.agent, image=False)
        runner_request = RunnerRequest(
            model_id=resolved.model_id,
            system_prompt="Return a JSON object with ok set to true.",
            input_payload={"ok": True},
            response_schema=_TEST_SCHEMA,
            schema_name="agent_test",
            temperature=0,
            max_output_tokens=32,
            timeout_seconds=30,
            effort=(resolved.effort.value if resolved.effort is not None else None),
        )
        try:
            result = await self._run(request.agent, runner_request, request_id)
        except AgentServiceError as exc:
            if exc.code is ErrorCode.UNAUTHORIZED:
                self.registry.set_auth_state(request.agent, AuthState.UNAUTHENTICATED)
            raise
        self.registry.set_auth_state(request.agent, AuthState.AUTHENTICATED)
        return TestOutput(
            ok=bool(result.payload.get("ok")),
            agent=request.agent,
            model_id=resolved.model_id,
            profile_id=request.profile_id,
            request_id=request_id,
            duration_seconds=result.duration_seconds,
        )

    async def generate(
        self, request: AgentGenerationInput, request_id: str
    ) -> AgentGenerationOutput:
        self._validate_schema(request.response_schema)
        runner = self._runner(request.agent)
        resolved = await self._resolve_profile(
            runner,
            request.agent,
            profile_id=request.profile_id,
            model_id=request.model_id,
        )
        await self._check_capability(resolved.profile, request.agent, image=False)
        runner_request = self._runner_request(request, resolved=resolved)
        result = await self._run(request.agent, runner_request, request_id)
        return self._output(request, result, request_id, profile_id=request.profile_id)

    async def analyze_images(
        self,
        request: AgentGenerationInput,
        images: Sequence[UploadFile],
        request_id: str,
    ) -> AgentGenerationOutput:
        if not images:
            raise AgentServiceError(
                ErrorCode.INVALID_REQUEST, "at least one image is required", 422
            )
        self._validate_schema(request.response_schema)
        runner = self._runner(request.agent)
        resolved = await self._resolve_profile(
            runner,
            request.agent,
            profile_id=request.profile_id,
            model_id=request.model_id,
        )
        await self._check_capability(resolved.profile, request.agent, image=True)
        try:
            async with self.concurrency.slot(request.agent.value):
                async with RequestWorkspace(root=self.workspace_root) as workspace:
                    image_paths: list[Path] = []
                    for index, image in enumerate(images, start=1):
                        if image.content_type is None:
                            raise AgentServiceError(
                                ErrorCode.INVALID_REQUEST, "image type is required", 422
                            )
                        try:
                            data = await image.read(self.workspace_limits.max_file_bytes + 1)
                            if len(data) > self.workspace_limits.max_file_bytes:
                                raise ValueError("image exceeds file size limit")
                            self._validate_image_bytes(data, image.content_type)
                            image_path = workspace.save_image(
                                data,
                                image.content_type,
                                index,
                                self.workspace_limits,
                            )
                        except (OSError, ValueError) as exc:
                            raise AgentServiceError(
                                ErrorCode.INVALID_REQUEST, "invalid image", 422
                            ) from exc
                        image_paths.append(image_path)
                    runner_request = self._runner_request(
                        request, tuple(image_paths), resolved=resolved
                    )
                    if workspace.path is None:
                        raise AgentServiceError(
                            ErrorCode.PROVIDER_UNAVAILABLE, "provider is unavailable", 503
                        )
                    active_runner = self.registry.for_workspace(request.agent, workspace.path)
                    if active_runner is None:
                        raise AgentServiceError(
                            ErrorCode.INVALID_REQUEST, "agent is not configured", 422
                        )
                    result = await self._run_inside_slot(active_runner, runner_request, request_id)
        except ConcurrencyLimitError as exc:
            raise AgentServiceError(ErrorCode.RATE_LIMITED, "service is busy", 429) from exc
        except OSError as exc:
            raise AgentServiceError(
                ErrorCode.PROVIDER_UNAVAILABLE, "provider is unavailable", 503
            ) from exc
        return self._output(request, result, request_id, profile_id=request.profile_id)

    async def _run(
        self, agent: AgentName, request: RunnerRequest, request_id: str
    ) -> RunnerResult:
        try:
            async with self.concurrency.slot(agent.value):
                workspace = RequestWorkspace(root=self.workspace_root)
                async with workspace:
                    if workspace.path is None:
                        raise AgentServiceError(
                            ErrorCode.PROVIDER_UNAVAILABLE, "provider is unavailable", 503
                        )
                    runner = self.registry.for_workspace(agent, workspace.path)
                    if runner is None:
                        raise AgentServiceError(
                            ErrorCode.INVALID_REQUEST, "agent is not configured", 422
                        )
                    return await self._run_inside_slot(runner, request, request_id)
        except ConcurrencyLimitError as exc:
            raise AgentServiceError(ErrorCode.RATE_LIMITED, "service is busy", 429) from exc
        except OSError as exc:
            raise AgentServiceError(
                ErrorCode.PROVIDER_UNAVAILABLE, "provider is unavailable", 503
            ) from exc

    async def _run_inside_slot(
        self, runner: AgentRunner, request: RunnerRequest, request_id: str
    ) -> RunnerResult:
        try:
            result = await runner.run(request)
        except RunnerError as exc:
            code, status = _RUNNER_STATUS.get(
                exc.code, (ErrorCode.PROVIDER_UNAVAILABLE, 503)
            )
            if code is ErrorCode.UNAUTHORIZED:
                self.registry.set_auth_state(runner.name, AuthState.UNAUTHENTICATED)
            raise AgentServiceError(code, self._safe_message(code), status) from exc
        except (TimeoutError, OSError) as exc:
            raise AgentServiceError(
                ErrorCode.PROVIDER_UNAVAILABLE, "provider is unavailable", 503
            ) from exc
        except ConcurrencyLimitError as exc:
            raise AgentServiceError(ErrorCode.RATE_LIMITED, "service is busy", 429) from exc
        except Exception as exc:
            raise AgentServiceError(
                ErrorCode.PROVIDER_UNAVAILABLE, "provider is unavailable", 503
            ) from exc
        if result.model_id != request.model_id:
            raise AgentServiceError(ErrorCode.INVALID_OUTPUT, "invalid runner output", 502)
        try:
            Draft202012Validator(request.response_schema).validate(result.payload)
        except Exception as exc:
            raise AgentServiceError(ErrorCode.INVALID_OUTPUT, "invalid runner output", 502) from exc
        return result

    def _runner(self, agent: AgentName) -> AgentRunner:
        runner = self.registry.get(agent)
        if runner is None:
            raise AgentServiceError(ErrorCode.INVALID_REQUEST, "agent is not configured", 422)
        return runner

    @staticmethod
    def _validate_schema(schema: dict[str, Any]) -> None:
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as exc:
            raise AgentServiceError(
                ErrorCode.INVALID_REQUEST, "response schema is invalid", 422
            ) from exc

    @staticmethod
    def _validate_image_bytes(data: bytes, mime_type: str) -> None:
        expected_format = _IMAGE_FORMATS.get(mime_type)
        if expected_format is None:
            raise ValueError("unsupported image type")
        try:
            with Image.open(BytesIO(data)) as image:
                if image.format != expected_format:
                    raise ValueError("image bytes do not match declared type")
                image.verify()
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
            raise ValueError("invalid image bytes") from exc

    async def _runner_capabilities(self, runner: AgentRunner) -> RunnerCapabilities:
        try:
            return await runner.capabilities()
        except Exception as exc:
            raise AgentServiceError(
                ErrorCode.PROVIDER_UNAVAILABLE, "provider is unavailable", 503
            ) from exc

    async def _resolve_profile(
        self,
        runner: AgentRunner,
        agent: AgentName,
        *,
        profile_id: str | None,
        model_id: str | None,
    ) -> ResolvedProfile:
        capabilities = await self._runner_capabilities(runner)
        if not capabilities.installed:
            raise AgentServiceError(ErrorCode.PROVIDER_UNAVAILABLE, "provider is unavailable", 503)
        if capabilities.agent is not agent:
            raise AgentServiceError(ErrorCode.INVALID_REQUEST, "agent is not configured", 422)
        if profile_id is not None:
            profiles = capabilities.profiles or []
            profile = next((item for item in profiles if item.profile_id == profile_id), None)
            if profile is None:
                raise AgentServiceError(ErrorCode.MODEL_NOT_FOUND, "model was not found", 404)
            if model_id is not None and model_id != profile.model_id:
                raise AgentServiceError(
                    ErrorCode.INVALID_REQUEST, "profile does not match model", 422
                )
            return ResolvedProfile(
                profile=profile, model_id=profile.model_id, effort=profile.effort
            )

        if model_id is None:
            raise AgentServiceError(ErrorCode.INVALID_REQUEST, "model was not provided", 422)
        profiles = [item for item in (capabilities.profiles or []) if item.model_id == model_id]
        if len(profiles) > 1:
            raise AgentServiceError(
                ErrorCode.INVALID_REQUEST, "a profile is required for this model", 422
            )
        if profiles:
            profile = profiles[0]
        else:
            model = next((item for item in capabilities.models if item.model_id == model_id), None)
            if model is None:
                raise AgentServiceError(ErrorCode.MODEL_NOT_FOUND, "model was not found", 404)
            profile = legacy_profile(
                agent,
                model_id,
                version=capabilities.version,
                supports_text_input=model.supports_text_input,
                supports_image_input=model.supports_image_input,
                supports_structured_output=model.supports_structured_output,
            )
        return ResolvedProfile(profile=profile, model_id=profile.model_id, effort=profile.effort)

    @staticmethod
    async def _check_capability(
        profile: AgentModelProfile, agent: AgentName, *, image: bool
    ) -> None:
        if profile.agent is not agent:
            raise AgentServiceError(ErrorCode.INVALID_REQUEST, "agent is not configured", 422)
        if (
            not profile.supports_text_input
            or not profile.supports_structured_output
            or (image and not profile.supports_image_input)
        ):
            raise AgentServiceError(
                ErrorCode.INVALID_REQUEST, "requested capability is unavailable", 422
            )

    @staticmethod
    def _safe_message(code: ErrorCode) -> str:
        return {
            ErrorCode.TIMEOUT: "runner timed out",
            ErrorCode.UNAUTHORIZED: "runner authorization failed",
            ErrorCode.RATE_LIMITED: "runner rate limit reached",
            ErrorCode.INVALID_REQUEST: "request could not be prepared",
            ErrorCode.INVALID_OUTPUT: "invalid runner output",
            ErrorCode.MODEL_NOT_FOUND: "model was not found",
            ErrorCode.PROVIDER_UNAVAILABLE: "provider is unavailable",
        }[code]

    @staticmethod
    def _runner_request(
        request: AgentGenerationInput,
        image_paths: tuple[Path, ...] = (),
        *,
        resolved: ResolvedProfile,
    ) -> RunnerRequest:
        return RunnerRequest(
            model_id=resolved.model_id,
            system_prompt=request.system_prompt,
            input_payload=request.input_payload,
            response_schema=request.response_schema,
            schema_name=request.schema_name,
            temperature=request.temperature,
            max_output_tokens=request.max_output_tokens,
            timeout_seconds=request.timeout_seconds,
            image_paths=image_paths,
            effort=(resolved.effort.value if resolved.effort is not None else None),
        )

    @staticmethod
    def _output(
        request: AgentGenerationInput,
        result: RunnerResult,
        request_id: str,
        *,
        profile_id: str | None,
    ) -> AgentGenerationOutput:
        return AgentGenerationOutput(
            payload=result.payload,
            agent=request.agent,
            model_id=result.model_id,
            profile_id=profile_id,
            request_id=request_id,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            duration_seconds=result.duration_seconds,
        )
