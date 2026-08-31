from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    agent_service_token: SecretStr
    host: str = "0.0.0.0"
    port: int = 9001
    agent_workspace_root: Path = Path("/tmp/fitsho-agent")
    agent_global_max_concurrency: int = Field(default=4, ge=1, le=64)
    agent_queue_wait_seconds: float = Field(default=5.0, ge=0, le=60)
    agent_antigravity_max_concurrency: int = Field(default=2, ge=1, le=64)
    agent_max_images: int = Field(default=5, ge=1, le=10)
    agent_max_file_bytes: int = Field(default=8 * 1024 * 1024, ge=1024, le=64 * 1024 * 1024)
    agent_max_total_bytes: int = Field(
        default=20 * 1024 * 1024, ge=1024, le=128 * 1024 * 1024
    )
    agent_antigravity_executable: str = "agy"
    agent_antigravity_models: tuple[str, ...] = ()
    agent_antigravity_supports_image_input: bool = False

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
