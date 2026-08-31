from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    agent_service_token: SecretStr
    host: str = "0.0.0.0"
    port: int = 9001

    @field_validator("agent_service_token")
    @classmethod
    def validate_token(cls, value: SecretStr) -> SecretStr:
        token = value.get_secret_value().strip()
        if len(token) < 32:
            raise ValueError("agent_service_token must contain at least 32 characters")
        return SecretStr(token)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
