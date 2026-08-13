from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho"
    frontend_origin: str = "http://localhost:5173"
    frontend_origins: str | None = None
    app_env: Literal["local", "test", "production"] = "local"
    cookie_secure: bool = True
    session_cookie_name: str = "__Host-fitsho_session"
    session_ttl_seconds: int = 60 * 60 * 24 * 7
    email_provider: Literal["fake", "smtp"] = "fake"
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = Field(default=None, repr=False)
    smtp_from_address: str | None = None
    smtp_use_tls: bool = True
    password_reset_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    sms_provider: Literal["fake", "kavenegar"] = "fake"
    kavenegar_api_key: SecretStr | None = Field(default=None, repr=False)
    kavenegar_base_url: str = "https://api.kavenegar.com/v1"
    kavenegar_sender: str | None = None
    sms_timeout_seconds: float = Field(default=10.0, gt=0, le=60)
    phone_otp_hmac_secret: SecretStr = Field(
        default=SecretStr("fitsho-local-phone-otp-secret-change-me"), repr=False
    )
    phone_otp_ttl_seconds: int = Field(default=300, ge=60, le=900)
    phone_otp_resend_cooldown_seconds: int = Field(default=60, ge=10, le=600)
    phone_otp_max_attempts: int = Field(default=5, ge=1, le=10)
    media_root: Path = Path("var/media")
    media_public_path: str = "/media"
    media_max_bytes: int = 20 * 1024 * 1024
    import_media_max_bytes: int = 24 * 1024 * 1024
    media_max_video_duration_seconds: float = 20.0
    media_read_chunk_bytes: int = 1024 * 1024
    body_photo_storage_root: Path = Path("var/private/body-photos")
    body_photo_max_bytes: int = Field(default=8 * 1024 * 1024, ge=1024, le=20 * 1024 * 1024)
    body_photo_max_pixels: int = Field(default=20_000_000, ge=1, le=40_000_000)
    body_photo_min_width: int = Field(default=256, ge=64, le=4096)
    body_photo_min_height: int = Field(default=512, ge=64, le=8192)
    body_photo_min_crop_top_ratio: float = Field(default=0.15, ge=0.05, le=0.5)
    body_photo_top_band_ratio: float = Field(default=0.2, ge=0.05, le=0.4)
    body_photo_min_luma_stddev: float = Field(default=8.0, ge=0.0, le=64.0)
    body_photo_min_top_band_luma_range: int = Field(default=16, ge=0, le=255)
    body_photo_min_top_band_edge_mean: float = Field(default=1.0, ge=0.0, le=64.0)
    body_photo_read_chunk_bytes: int = Field(default=1024 * 1024, ge=1024, le=4 * 1024 * 1024)
    food_photo_storage_root: Path = Path("var/private/food-photos")
    food_photo_max_bytes: int = Field(default=8 * 1024 * 1024, ge=1024, le=20 * 1024 * 1024)
    food_photo_max_pixels: int = Field(default=20_000_000, ge=1, le=40_000_000)
    food_photo_retention_days: int = Field(default=30, ge=1, le=365)
    food_photo_rate_limit: int = Field(default=10, ge=1, le=1000)
    nutrition_lab_storage_root: Path = Path("var/private/nutrition-labs")
    nutrition_lab_max_bytes: int = Field(default=12 * 1024 * 1024, ge=1024, le=30 * 1024 * 1024)
    nutrition_lab_max_pixels: int = Field(default=20_000_000, ge=1, le=40_000_000)
    nutrition_lab_retention_days: int = Field(default=365 * 7, ge=30, le=365 * 20)
    nutrition_lab_upload_rate_limit: int = Field(default=20, ge=1, le=1000)
    nutrition_upload_rate_window_seconds: int = Field(default=3600, ge=60, le=86400)
    private_file_access_ttl_seconds: int = Field(default=300, ge=30, le=900)
    private_file_signing_key: SecretStr = Field(
        default=SecretStr("fitsho-local-private-file-signing-key-change-me"), repr=False
    )
    ffprobe_path: str = "ffprobe"
    ffprobe_timeout_seconds: float = 5.0
    opencode_zen_api_key: SecretStr | None = Field(default=None, repr=False)
    opencode_zen_base_url: str = "https://opencode.ai/zen/v1"
    opencode_zen_model: str = "gpt-5.6-terra"
    opencode_zen_timeout_seconds: float = Field(default=30.0, gt=0, le=120)
    opencode_zen_proxy_url: str | None = Field(default=None, max_length=500, repr=False)
    ai_credential_encryption_key: SecretStr | None = Field(default=None, repr=False)
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_timeout_seconds: float = Field(default=45.0, gt=0, le=180)
    openrouter_proxy_url: str | None = Field(default=None, max_length=500, repr=False)
    ai_model_catalog_ttl_seconds: int = Field(default=3600, ge=60, le=86400)
    workout_prompt_version: str = "v1"
    workout_policy_version: str = "v1"
    workout_catalog_programming_version: str = "v1"
    workout_max_repair_attempts: int = Field(default=1, ge=0, le=1)
    workout_generation_cooldown_seconds: int = Field(default=0, ge=0, le=3600)
    workout_deterministic_fallback_enabled: bool = True
    workout_max_candidates: int = Field(default=80, ge=3, le=200)
    workout_max_request_bytes: int = Field(default=262144, ge=1024, le=1048576)
    workout_warmup_minutes: int = Field(default=5, ge=0, le=30)
    food_price_update_enabled: bool = True
    food_price_update_timezone: str = "Asia/Tehran"
    food_price_update_hour: int = Field(default=12, ge=0, le=23)
    food_price_update_minute: int = Field(default=0, ge=0, le=59)
    food_price_provider_timeout_seconds: float = Field(default=15.0, gt=0, le=60)
    food_price_provider_retries: int = Field(default=3, ge=1, le=5)
    food_price_public_source_url: str | None = Field(default=None, max_length=500, repr=False)
    food_price_api_key: SecretStr | None = Field(default=None, repr=False)
    food_price_api_base_url: str | None = Field(default=None, max_length=500, repr=False)
    food_price_persianapi_enabled: bool = False
    food_price_persianapi_api_key: SecretStr | None = Field(default=None, repr=False)
    food_price_basalam_api_enabled: bool = False
    food_price_basalam_api_key: SecretStr | None = Field(default=None, repr=False)
    food_price_provider_api_enabled: bool = False
    food_price_provider_api_key: SecretStr | None = Field(default=None, repr=False)
    food_price_provider_base_url: str | None = Field(default=None, max_length=500, repr=False)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def allowed_frontend_origins(self) -> tuple[str, ...]:
        configured_origins = (
            tuple(origin.strip().rstrip("/") for origin in self.frontend_origins.split(","))
            if self.frontend_origins is not None
            else ()
        )
        return tuple(
            dict.fromkeys(
                origin for origin in (self.frontend_origin, *configured_origins) if origin
            )
        )

    @model_validator(mode="after")
    def enforce_private_body_photo_storage(self) -> Self:
        public_root = self.media_root.resolve()
        private_root = self.body_photo_storage_root.resolve()
        if private_root == public_root or private_root.is_relative_to(public_root):
            raise ValueError("Body photo storage must be outside public media storage")
        food_private_root = self.food_photo_storage_root.resolve()
        if food_private_root == public_root or food_private_root.is_relative_to(public_root):
            raise ValueError("Food photo storage must be outside public media storage")
        lab_root = self.nutrition_lab_storage_root.resolve()
        if lab_root == public_root or lab_root.is_relative_to(public_root):
            raise ValueError("Nutrition lab storage must be outside public media storage")
        return self

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
        if self.email_provider != "smtp" or not self.smtp_host or not self.smtp_from_address:
            raise ValueError("Production requires a configured SMTP email provider")
        if self.sms_provider != "kavenegar" or self.kavenegar_api_key is None:
            raise ValueError("Production requires a configured Kavenegar SMS provider")
        otp_secret = self.phone_otp_hmac_secret.get_secret_value()
        if otp_secret == "fitsho-local-phone-otp-secret-change-me" or len(otp_secret) < 32:
            raise ValueError("Production requires a strong phone OTP HMAC secret")
        signing_key = self.private_file_signing_key.get_secret_value()
        if (
            signing_key == "fitsho-local-private-file-signing-key-change-me"
            or len(signing_key) < 32
        ):
            raise ValueError("Production requires a strong private file signing key")
        self.frontend_origin = f"https://{origin.netloc}"
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
