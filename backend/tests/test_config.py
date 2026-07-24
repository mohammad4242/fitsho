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
