from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.router import router as auth_router
from app.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    app = FastAPI(title="Fitsho API")
    app.dependency_overrides[get_settings] = lambda: active_settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[active_settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(auth_router)
    return app


app = create_app()
