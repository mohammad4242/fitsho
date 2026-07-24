from functools import lru_cache
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho"
    frontend_origin: str = "http://localhost:5173"
    app_env: Literal["local", "test", "production"] = "local"
    cookie_secure: bool = True
    session_cookie_name: str = "__Host-fitsho_session"
    session_ttl_seconds: int = 60 * 60 * 24 * 7

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
