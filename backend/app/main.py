from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.admin.router import router as admin_router
from app.auth.router import router as auth_router
from app.body_analysis.admin_config.router import router as admin_ai_settings_router
from app.body_analysis.router import admin_router as body_analysis_admin_router
from app.body_analysis.router import review_router as body_analysis_review_router
from app.body_analysis.router import router as body_analysis_router
from app.body_photos.router import router as body_photo_router
from app.config import Settings, get_settings
from app.exercises.router import router as exercises_router
from app.profile.router import router as profile_router
from app.workouts.router import router as workout_plans_router


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    active_settings.media_root.mkdir(parents=True, exist_ok=True)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        zen_timeout = httpx.Timeout(active_settings.opencode_zen_timeout_seconds)
        ai_timeout = httpx.Timeout(active_settings.openrouter_timeout_seconds)
        async with (
            httpx.AsyncClient(
                timeout=zen_timeout,
                proxy=active_settings.opencode_zen_proxy_url,
                trust_env=False,
            ) as zen_client,
            httpx.AsyncClient(
                timeout=ai_timeout,
                proxy=active_settings.openrouter_proxy_url,
                trust_env=False,
            ) as ai_client,
        ):
            app.state.zen_http_client = zen_client
            app.state.ai_http_client = ai_client
            yield

    app = FastAPI(title="Fitsho API", lifespan=lifespan)
    app.dependency_overrides[get_settings] = lambda: active_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[active_settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["DELETE", "GET", "PATCH", "POST", "PUT"],
        allow_headers=[
            "Content-Type",
            "X-Fitsho-Client-Crop-Confirmed",
            "X-Fitsho-Client-Crop-Confidence",
            "X-Fitsho-Original-Height",
            "X-Fitsho-Crop-Top",
            "X-Fitsho-Crop-Bottom",
            "X-Fitsho-Processed-SHA256",
            "X-Fitsho-Crop-Evidence-SHA256",
        ],
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
    app.include_router(body_photo_router)
    app.include_router(body_analysis_router)
    app.include_router(profile_router)
    app.include_router(workout_plans_router)
    app.include_router(exercises_router)
    app.include_router(admin_router)
    app.include_router(admin_ai_settings_router)
    app.include_router(body_analysis_review_router)
    app.include_router(body_analysis_admin_router)
    app.mount(
        active_settings.media_public_path,
        StaticFiles(directory=active_settings.media_root),
        name="exercise-media",
    )
    return app


app = create_app()
