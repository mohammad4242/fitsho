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


def test_production_settings_accept_secure_cookie_contract() -> None:
    settings = Settings(
        app_env="production",
        frontend_origin="https://fitsho.example",
        cookie_secure=True,
        session_cookie_name="__Host-fitsho_session",
    )

    assert settings.app_env == "production"


@pytest.mark.parametrize(
    ("override", "expected_message"),
    [
        ({"frontend_origin": "http://fitsho.example"}, "HTTPS frontend origin"),
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
    }
    values.update(override)

    with pytest.raises(ValidationError, match=expected_message):
        Settings(**values)  # type: ignore[arg-type]
