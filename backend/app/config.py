from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho"
    frontend_origin: str = "http://localhost:5173"
    app_env: Literal["local", "test", "production"] = "local"
    cookie_secure: bool = True
    session_cookie_name: str = "__Host-fitsho_session"
    session_ttl_seconds: int = 60 * 60 * 24 * 7
    media_root: Path = Path("var/media")
    media_public_path: str = "/media"
    media_max_bytes: int = 20 * 1024 * 1024
    media_max_video_duration_seconds: float = 20.0
    media_read_chunk_bytes: int = 1024 * 1024
    ffprobe_path: str = "ffprobe"
    ffprobe_timeout_seconds: float = 5.0
    opencode_zen_api_key: SecretStr | None = Field(default=None, repr=False)
    opencode_zen_base_url: str = "https://opencode.ai/zen/v1"
    opencode_zen_model: str = "gpt-5.6-terra"
    opencode_zen_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    opencode_zen_proxy_url: str | None = Field(default=None, max_length=500, repr=False)
    workout_prompt_version: str = "v1"
    workout_policy_version: str = "v1"
    workout_catalog_programming_version: str = "v1"
    workout_max_repair_attempts: int = Field(default=1, ge=0, le=1)
    workout_generation_cooldown_seconds: int = Field(default=300, ge=0, le=3600)
    workout_max_candidates: int = Field(default=80, ge=3, le=200)
    workout_max_request_bytes: int = Field(default=262144, ge=1024, le=1048576)
    workout_warmup_minutes: int = Field(default=5, ge=0, le=30)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def enforce_production_cookie_contract(self) -> Self:
        if self.app_env != "production":
            return self
        origin = urlsplit(self.frontend_origin)
        if origin.scheme != "https":
            raise ValueError("Production requires an HTTPS frontend origin")
        if origin.hostname is None:
            raise ValueError("Production requires a complete frontend origin")
        if (
            origin.username is not None
            or origin.password is not None
            or origin.path not in {"", "/"}
            or origin.query
            or origin.fragment
        ):
            raise ValueError(
                "Production requires an origin without credentials, path, query, or fragment"
            )
        if not self.cookie_secure:
            raise ValueError("Production requires secure cookies")
        if self.session_cookie_name != "__Host-fitsho_session":
            raise ValueError("Production requires the __Host-fitsho_session cookie name")
        self.frontend_origin = f"https://{origin.netloc}"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
