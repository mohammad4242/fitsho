from sqlalchemy import inspect
from sqlalchemy.orm import Session


def test_notification_tables_are_migrated(db: Session) -> None:
    inspector = inspect(db.get_bind())
    tables = set(inspector.get_table_names())

    assert {
        "notification_devices",
        "notification_device_tokens",
        "notification_preferences",
    }.issubset(tables)

    device_columns = {column["name"] for column in inspector.get_columns("notification_devices")}
    assert {"user_id", "device_id", "platform", "app_version", "last_seen_at"}.issubset(
        device_columns
    )
    token_columns = {
        column["name"] for column in inspector.get_columns("notification_device_tokens")
    }
    assert {"device_id", "provider", "token_hash", "token_value", "invalid_at"}.issubset(
        token_columns
    )
    preference_columns = {
        column["name"] for column in inspector.get_columns("notification_preferences")
    }
    assert {
        "user_id",
        "enabled",
        "approved_plans",
        "required_reviews",
        "body_analysis",
        "cycle_reminders",
        "physician_decisions",
    }.issubset(preference_columns)

    outbox_columns = {
        column["name"] for column in inspector.get_columns("notification_outbox_events")
    }
    assert {
        "user_id",
        "event_type",
        "category",
        "deduplication_key",
        "payload",
        "status",
        "locked_at",
        "processed_at",
    }.issubset(outbox_columns)
    delivery_columns = {
        column["name"] for column in inspector.get_columns("notification_event_deliveries")
    }
    assert {"event_id", "token_id", "status", "created_at"}.issubset(delivery_columns)
