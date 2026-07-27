import os
import subprocess
import sys
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.session import get_db
from app.main import create_app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://fitsho:fitsho@localhost:5432/fitsho_test",
)


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    environment = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        env=environment,
    )
    yield


@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine(TEST_DATABASE_URL)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        database_url=TEST_DATABASE_URL,
        frontend_origin="http://localhost:5173",
        app_env="test",
        cookie_secure=False,
        session_cookie_name="fitsho_session",
        session_ttl_seconds=604800,
    )


@pytest.fixture
def client(db: Session, test_settings: Settings) -> Iterator[TestClient]:
    app = create_app(test_settings)

    def override_db() -> Iterator[Session]:
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
