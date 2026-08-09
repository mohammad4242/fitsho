import pytest
from pydantic import ValidationError

from app.config import Settings


def test_settings_accept_explicit_environment_values() -> None:
    settings = Settings(
        database_url="postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho",
        frontend_origin="http://localhost:5173",
        app_env="test",
        cookie_secure=False,
        session_cookie_name="fitsho_session",
    )

    assert settings.session_ttl_seconds == 604800
    assert settings.frontend_origin == "http://localhost:5173"


def test_local_settings_accept_multiple_explicit_frontend_origins() -> None:
    settings = Settings(
        app_env="local",
        frontend_origin="http://localhost:5173",
        frontend_origins="http://localhost:5173,http://100.97.78.5:5173",
        cookie_secure=False,
        session_cookie_name="fitsho_session",
    )

    assert settings.allowed_frontend_origins == (
        "http://localhost:5173",
        "http://100.97.78.5:5173",
    )


def test_production_settings_accept_secure_cookie_contract() -> None:
    settings = Settings(
        app_env="production",
        frontend_origin="https://fitsho.example",
        cookie_secure=True,
        session_cookie_name="__Host-fitsho_session",
        private_file_signing_key="production-private-file-signing-key-for-tests",
    )

    assert settings.app_env == "production"


def test_production_settings_normalize_a_trailing_origin_slash() -> None:
    settings = Settings(
        app_env="production",
        frontend_origin="https://fitsho.example/",
        cookie_secure=True,
        session_cookie_name="__Host-fitsho_session",
        private_file_signing_key="production-private-file-signing-key-for-tests",
    )

    assert settings.frontend_origin == "https://fitsho.example"


@pytest.mark.parametrize(
    ("override", "expected_message"),
    [
        ({"frontend_origin": "http://fitsho.example"}, "HTTPS frontend origin"),
        ({"frontend_origin": "https://"}, "complete frontend origin"),
        (
            {"frontend_origin": "https://fitsho.example/app"},
            "origin without credentials, path, query, or fragment",
        ),
        (
            {"frontend_origin": "https://user@fitsho.example"},
            "origin without credentials, path, query, or fragment",
        ),
        (
            {"frontend_origin": "https://fitsho.example?source=config"},
            "origin without credentials, path, query, or fragment",
        ),
        ({"cookie_secure": False}, "secure cookies"),
        ({"session_cookie_name": "fitsho_session"}, "__Host-fitsho_session"),
    ],
)
def test_production_settings_reject_insecure_cookie_contract(
    override: dict[str, object],
    expected_message: str,
) -> None:
    values: dict[str, object] = {
        "app_env": "production",
        "frontend_origin": "https://fitsho.example",
        "cookie_secure": True,
        "session_cookie_name": "__Host-fitsho_session",
        "private_file_signing_key": "production-private-file-signing-key-for-tests",
    }
    values.update(override)

    with pytest.raises(ValidationError, match=expected_message):
        Settings(**values)  # type: ignore[arg-type]


def test_production_settings_reject_default_private_file_signing_key() -> None:
    with pytest.raises(ValidationError, match="strong private file signing key"):
        Settings(
            app_env="production",
            frontend_origin="https://fitsho.example",
            cookie_secure=True,
            session_cookie_name="__Host-fitsho_session",
        )


def test_settings_redact_zen_api_key_in_repr() -> None:
    settings = Settings(opencode_zen_api_key="test-secret-key")

    assert "test-secret-key" not in repr(settings)
    assert settings.workout_max_repair_attempts == 1
    assert settings.workout_generation_cooldown_seconds == 0
    assert settings.workout_deterministic_fallback_enabled is True
    assert settings.workout_max_candidates == 80
    assert settings.workout_max_request_bytes == 262144
    assert settings.workout_warmup_minutes == 5


def test_settings_accept_an_explicit_zen_proxy_url() -> None:
    settings = Settings(opencode_zen_proxy_url="socks5://127.0.0.1:10808")

    assert settings.opencode_zen_proxy_url == "socks5://127.0.0.1:10808"
