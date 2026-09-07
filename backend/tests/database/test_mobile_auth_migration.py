from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect
from sqlalchemy.orm import Session


def test_mobile_auth_token_tables_are_migrated(db: Session) -> None:
    inspector = inspect(db.get_bind())
    tables = set(inspector.get_table_names())

    assert {
        "mobile_token_families",
        "mobile_access_tokens",
        "mobile_refresh_tokens",
        "mobile_auth_events",
    }.issubset(tables)

    family_columns = {column["name"] for column in inspector.get_columns("mobile_token_families")}
    assert {
        "user_id",
        "device_id",
        "platform",
        "app_version",
        "revoked_at",
    }.issubset(family_columns)

    refresh_columns = {column["name"] for column in inspector.get_columns("mobile_refresh_tokens")}
    assert {"family_id", "token_hash", "expires_at", "used_at", "replaced_by_id"}.issubset(
        refresh_columns
    )

    event_columns = {column["name"] for column in inspector.get_columns("mobile_auth_events")}
    assert {"user_id", "family_id", "event_type", "event_data", "created_at"}.issubset(
        event_columns
    )


def test_mobile_auth_migration_downgrades_and_upgrades_cleanly(db: Session) -> None:
    event_path = (
        Path(__file__).parents[2]
        / "alembic/versions/20260907_128_add_mobile_auth_events.py"
    )
    event_spec = spec_from_file_location("mobile_auth_event_migration_for_tokens", event_path)
    assert event_spec is not None and event_spec.loader is not None
    event_migration = module_from_spec(event_spec)
    event_spec.loader.exec_module(event_migration)
    event_migration.op = Operations(MigrationContext.configure(db.connection()))
    event_migration.downgrade()

    path = Path(__file__).parents[2] / "alembic/versions/20260907_127_add_mobile_token_tables.py"
    spec = spec_from_file_location("mobile_auth_migration", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.op = Operations(MigrationContext.configure(db.connection()))

    migration.downgrade()
    assert not {
        "mobile_token_families",
        "mobile_access_tokens",
        "mobile_refresh_tokens",
    }.intersection(inspect(db.get_bind()).get_table_names())

    migration.upgrade()
    assert {
        "mobile_token_families",
        "mobile_access_tokens",
        "mobile_refresh_tokens",
    }.issubset(inspect(db.get_bind()).get_table_names())

    event_migration.op = Operations(MigrationContext.configure(db.connection()))
    event_migration.upgrade()


def test_mobile_auth_event_migration_downgrades_and_upgrades_cleanly(db: Session) -> None:
    path = Path(__file__).parents[2] / "alembic/versions/20260907_128_add_mobile_auth_events.py"
    spec = spec_from_file_location("mobile_auth_event_migration", path)
    assert spec is not None and spec.loader is not None
    migration = module_from_spec(spec)
    spec.loader.exec_module(migration)
    migration.op = Operations(MigrationContext.configure(db.connection()))

    migration.downgrade()
    assert "mobile_auth_events" not in inspect(db.get_bind()).get_table_names()

    migration.upgrade()
    assert "mobile_auth_events" in inspect(db.get_bind()).get_table_names()
