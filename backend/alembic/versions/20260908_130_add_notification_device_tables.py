"""add notification devices, tokens, and preferences"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260908_130"
down_revision: str | Sequence[str] | None = "20260908_129"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("app_version", sa.String(length=64), nullable=False),
        sa.Column("device_name", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "char_length(btrim(device_id)) BETWEEN 1 AND 128",
            name="ck_notification_devices_device_id_length",
        ),
        sa.CheckConstraint(
            "platform IN ('android', 'ios')",
            name="ck_notification_devices_platform",
        ),
        sa.CheckConstraint(
            "char_length(btrim(app_version)) BETWEEN 1 AND 64",
            name="ck_notification_devices_app_version_length",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "device_id", name="uq_notification_devices_user_device"),
    )
    op.create_index(
        "ix_notification_devices_user_id_created_at",
        "notification_devices",
        ["user_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "notification_device_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("token_value", sa.String(length=4096), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("invalid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalid_reason", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "provider IN ('fcm')",
            name="ck_notification_device_tokens_provider",
        ),
        sa.CheckConstraint(
            "char_length(btrim(token_value)) BETWEEN 1 AND 4096",
            name="ck_notification_device_tokens_value_length",
        ),
        sa.CheckConstraint(
            "char_length(token_hash) = 64",
            name="ck_notification_device_tokens_hash_length",
        ),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["notification_devices.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "token_hash",
            name="uq_notification_device_tokens_provider_hash",
        ),
    )
    op.create_index(
        "ix_notification_device_tokens_device_provider",
        "notification_device_tokens",
        ["device_id", "provider"],
        unique=False,
    )

    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("approved_plans", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("required_reviews", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("body_analysis", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("cycle_reminders", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("physician_decisions", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_index(
        "ix_notification_device_tokens_device_provider",
        table_name="notification_device_tokens",
    )
    op.drop_table("notification_device_tokens")
    op.drop_index(
        "ix_notification_devices_user_id_created_at",
        table_name="notification_devices",
    )
    op.drop_table("notification_devices")
