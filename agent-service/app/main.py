from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from .config import Settings, get_settings
from .errors import AgentServiceError, handle_service_error
from .schemas import CapabilitiesResponse, ErrorCode, ErrorDetail, ErrorEnvelope
from .security import require_internal_auth


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Fitsho Agent Service")
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings

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

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/capabilities", response_model=CapabilitiesResponse)
    async def capabilities(_: None = Depends(require_internal_auth)) -> CapabilitiesResponse:
        return CapabilitiesResponse(runners=[])

    return app


app = create_app()
