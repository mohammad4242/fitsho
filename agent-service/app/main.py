from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from .auth.adapters.antigravity import AntigravityAuthAdapter
from .auth.adapters.claude import ClaudeAuthAdapter
from .auth.adapters.codex import CodexAuthAdapter
from .auth.manager import AuthManager, AuthManagerError
from .auth.schemas import (
    AuthActiveCancellationResponse,
    AuthInputRequest,
    AuthSessionView,
    AuthStartRequest,
)
from .concurrency import ConcurrencyController
from .config import Settings, get_settings
from .errors import AgentServiceError, handle_service_error
from .observability import emit_log
from .runners.registry import RunnerRegistry
from .schemas import (
    AgentGenerationInput,
    AgentGenerationOutput,
    AgentName,
    CapabilitiesResponse,
    ErrorCode,
    ErrorDetail,
    ErrorEnvelope,
    TestOutput,
    TestRequest,
)
from .security import require_internal_auth
from .service import AgentService
from .workspace import WorkspaceLimits


def create_app(
    settings: Settings | None = None,
    registry: RunnerRegistry | None = None,
    concurrency: ConcurrencyController | None = None,
    auth_manager: AuthManager | None = None,
) -> FastAPI:
    effective_settings = settings or get_settings()

    runner_registry = registry or RunnerRegistry.from_settings(effective_settings)
    effective_auth_manager = auth_manager or AuthManager(
        {
            AgentName.ANTIGRAVITY: AntigravityAuthAdapter(
                effective_settings.agent_antigravity_executable
            ),
            AgentName.CODEX: CodexAuthAdapter(effective_settings.agent_codex_executable),
            AgentName.CLAUDE: ClaudeAuthAdapter(effective_settings.agent_claude_executable),
        },
        workspace=Path(effective_settings.agent_workspace_root),
        ttl_seconds=effective_settings.agent_auth_session_ttl_seconds,
        max_output_bytes=effective_settings.agent_auth_max_output_bytes,
        state_callback=runner_registry.set_auth_state,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await effective_auth_manager.shutdown()

    app = FastAPI(title="Fitsho Agent Service", lifespan=lifespan)
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings
    controller = concurrency or ConcurrencyController(
        global_limit=effective_settings.agent_global_max_concurrency,
        runner_limits={
            "antigravity": effective_settings.agent_antigravity_max_concurrency,
            "codex": effective_settings.agent_codex_max_concurrency,
            "claude": effective_settings.agent_claude_max_concurrency,
        },
        queue_wait_seconds=effective_settings.agent_queue_wait_seconds,
    )
    agent_service = AgentService(
        registry=runner_registry,
        concurrency=controller,
        workspace_root=Path(effective_settings.agent_workspace_root),
        workspace_limits=WorkspaceLimits(
            max_images=effective_settings.agent_max_images,
            max_file_bytes=effective_settings.agent_max_file_bytes,
            max_total_bytes=effective_settings.agent_max_total_bytes,
        ),
    )
    app.state.agent_service = agent_service
    app.state.auth_manager = effective_auth_manager

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.request_id = str(uuid4())
        started = perf_counter()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            content_length = request.headers.get("content-length")
            try:
                input_bytes = max(0, int(content_length)) if content_length is not None else None
            except ValueError:
                input_bytes = None
            is_auth_endpoint = request.url.path.startswith("/v1/auth/")
            telemetry = {
                "request_id": request.state.request_id,
                "endpoint": request.url.path,
                "duration_ms": round((perf_counter() - started) * 1000, 3),
                "status": response.status_code if response is not None else "error",
            }
            telemetry_fields = ("agent", "error_code") if is_auth_endpoint else (
                "agent",
                "model",
                "task_kind",
                "image_count",
                "input_tokens",
                "output_tokens",
                "error_code",
            )
            if not is_auth_endpoint:
                telemetry["input_bytes"] = input_bytes
            for field in telemetry_fields:
                value = getattr(request.state, field, None)
                if value is not None:
                    telemetry[field] = value
            emit_log(telemetry)
            if response is not None:
                response.headers["X-Request-ID"] = request.state.request_id

    @app.exception_handler(AgentServiceError)
    async def service_error_handler(request: Request, exc: AgentServiceError) -> JSONResponse:
        request.state.error_code = exc.code.value
        return await handle_service_error(request, exc)

    @app.exception_handler(AuthManagerError)
    async def auth_error_handler(request: Request, exc: AuthManagerError) -> JSONResponse:
        try:
            code = ErrorCode(exc.code)
        except ValueError:
            code = ErrorCode.AUTH_UNAVAILABLE
        request.state.error_code = code.value
        payload = ErrorEnvelope(
            error=ErrorDetail(
                code=code,
                message=exc.safe_message,
                request_id=request.state.request_id,
            )
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump(mode="json"))

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if exc.status_code == 401:
            request.state.error_code = ErrorCode.UNAUTHORIZED.value
            payload = ErrorEnvelope(
                error=ErrorDetail(
                    code=ErrorCode.UNAUTHORIZED,
                    message="unauthorized",
                    request_id=request.state.request_id,
                )
            )
            return JSONResponse(
                status_code=401,
                content=payload.model_dump(mode="json"),
                headers={"WWW-Authenticate": "Bearer"},
            )
        code = (
            ErrorCode.INVALID_REQUEST
            if 400 <= exc.status_code < 500
            else ErrorCode.PROVIDER_UNAVAILABLE
        )
        request.state.error_code = code.value
        payload = ErrorEnvelope(
            error=ErrorDetail(
                code=code,
                message="request failed",
                request_id=request.state.request_id,
            )
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=payload.model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        del exc
        request.state.error_code = ErrorCode.INVALID_REQUEST.value
        payload = ErrorEnvelope(
            error=ErrorDetail(
                code=ErrorCode.INVALID_REQUEST,
                message="invalid request",
                request_id=request.state.request_id,
            )
        )
        return JSONResponse(status_code=422, content=payload.model_dump(mode="json"))

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, _error: Exception) -> JSONResponse:
        request.state.error_code = ErrorCode.PROVIDER_UNAVAILABLE.value
        payload = ErrorEnvelope(
            error=ErrorDetail(
                code=ErrorCode.PROVIDER_UNAVAILABLE,
                message="provider is unavailable",
                request_id=request.state.request_id,
            )
        )
        return JSONResponse(status_code=503, content=payload.model_dump(mode="json"))

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/capabilities", response_model=CapabilitiesResponse)
    async def capabilities(_: None = Depends(require_internal_auth)) -> CapabilitiesResponse:
        return CapabilitiesResponse(runners=await agent_service.capabilities())

    @app.post("/v1/auth/start", response_model=AuthSessionView)
    async def auth_start(
        request: Request,
        payload: AuthStartRequest,
        _: None = Depends(require_internal_auth),
    ) -> AuthSessionView:
        request.state.agent = payload.agent.value
        request.state.task_kind = "auth"
        return await effective_auth_manager.start(payload.agent)

    @app.post("/v1/auth/cancel-active", response_model=AuthActiveCancellationResponse)
    async def auth_cancel_active(
        request: Request,
        payload: AuthStartRequest,
        _: None = Depends(require_internal_auth),
    ) -> AuthActiveCancellationResponse:
        request.state.agent = payload.agent.value
        request.state.task_kind = "auth"
        canceled = await effective_auth_manager.cancel_active(payload.agent)
        return AuthActiveCancellationResponse(agent=payload.agent, canceled=canceled)

    @app.get("/v1/auth/{session_id}", response_model=AuthSessionView)
    async def auth_status(
        request: Request,
        session_id: UUID,
        _: None = Depends(require_internal_auth),
    ) -> AuthSessionView:
        request.state.task_kind = "auth"
        view = await effective_auth_manager.get(session_id)
        request.state.agent = view.agent.value
        return view

    @app.post("/v1/auth/{session_id}/input", response_model=AuthSessionView)
    async def auth_input(
        request: Request,
        session_id: UUID,
        payload: AuthInputRequest,
        _: None = Depends(require_internal_auth),
    ) -> AuthSessionView:
        request.state.task_kind = "auth"
        view = await effective_auth_manager.submit_input(session_id, payload.value)
        request.state.agent = view.agent.value
        return view

    @app.delete("/v1/auth/{session_id}", response_model=AuthSessionView)
    async def auth_cancel(
        request: Request,
        session_id: UUID,
        _: None = Depends(require_internal_auth),
    ) -> AuthSessionView:
        request.state.task_kind = "auth"
        view = await effective_auth_manager.cancel(session_id)
        request.state.agent = view.agent.value
        return view

    @app.post("/v1/test", response_model=TestOutput)
    async def test_runner(
        request: Request,
        payload: TestRequest,
        _: None = Depends(require_internal_auth),
    ) -> TestOutput:
        request.state.agent = payload.agent.value
        request.state.model = payload.model_id
        request.state.task_kind = "test"
        return await agent_service.test(payload, request.state.request_id)

    @app.post("/v1/generate", response_model=AgentGenerationOutput)
    async def generate(
        request: Request,
        payload: AgentGenerationInput,
        _: None = Depends(require_internal_auth),
    ) -> AgentGenerationOutput:
        request.state.agent = payload.agent.value
        request.state.model = payload.model_id
        request.state.task_kind = "generate"
        result = await agent_service.generate(payload, request.state.request_id)
        request.state.input_tokens = result.input_tokens
        request.state.output_tokens = result.output_tokens
        return result

    @app.post("/v1/analyze-images", response_model=AgentGenerationOutput)
    async def analyze_images(
        request: Request,
        metadata: Annotated[str, Form(...)],
        images: Annotated[list[UploadFile], File(...)],
        _: None = Depends(require_internal_auth),
    ) -> AgentGenerationOutput:
        try:
            payload = AgentGenerationInput.model_validate_json(metadata)
        except (ValueError, TypeError) as exc:
            raise AgentServiceError(ErrorCode.INVALID_REQUEST, "invalid metadata", 422) from exc
        request.state.agent = payload.agent.value
        request.state.model = payload.model_id
        request.state.task_kind = "analyze_images"
        request.state.image_count = len(images)
        result = await agent_service.analyze_images(payload, images, request.state.request_id)
        request.state.input_tokens = result.input_tokens
        request.state.output_tokens = result.output_tokens
        return result

    return app


app = create_app()
