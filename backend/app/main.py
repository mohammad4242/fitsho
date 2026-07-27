from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.auth.router import router as auth_router
from app.config import Settings, get_settings
from app.exercises.router import router as exercises_router
from app.profile.router import router as profile_router


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    app = FastAPI(title="Fitsho API")
    app.dependency_overrides[get_settings] = lambda: active_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[active_settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(
        _request: Request,
        _error: SQLAlchemyError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Service temporarily unavailable"},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        safe_errors = [
            {
                "type": item["type"],
                "loc": item["loc"],
                "msg": item["msg"],
            }
            for item in error.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": safe_errors},
        )

    app.include_router(auth_router)
    app.include_router(profile_router)
    app.include_router(exercises_router)
    return app


app = create_app()
