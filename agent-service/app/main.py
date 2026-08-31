from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from .concurrency import ConcurrencyController
from .config import Settings, get_settings
from .errors import AgentServiceError, handle_service_error
from .runners.registry import RunnerRegistry
from .schemas import (
    AgentGenerationInput,
    AgentGenerationOutput,
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
) -> FastAPI:
    app = FastAPI(title="Fitsho Agent Service")
    effective_settings = settings or get_settings()
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings

    runner_registry = registry or RunnerRegistry.from_settings(effective_settings)
    controller = concurrency or ConcurrencyController(
        global_limit=effective_settings.agent_global_max_concurrency,
        runner_limits={
            "antigravity": effective_settings.agent_antigravity_max_concurrency,
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

    @app.middleware("http")
    async def add_request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(AgentServiceError)
    async def service_error_handler(request: Request, exc: AgentServiceError) -> JSONResponse:
        return await handle_service_error(request, exc)

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if exc.status_code == 401:
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

    @app.post("/v1/test", response_model=TestOutput)
    async def test_runner(
        request: Request,
        payload: TestRequest,
        _: None = Depends(require_internal_auth),
    ) -> TestOutput:
        return await agent_service.test(payload, request.state.request_id)

    @app.post("/v1/generate", response_model=AgentGenerationOutput)
    async def generate(
        request: Request,
        payload: AgentGenerationInput,
        _: None = Depends(require_internal_auth),
    ) -> AgentGenerationOutput:
        return await agent_service.generate(payload, request.state.request_id)

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
        return await agent_service.analyze_images(payload, images, request.state.request_id)

    return app


app = create_app()
