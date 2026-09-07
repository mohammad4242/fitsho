"""add the transactional notification outbox and delivery fan-out"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260908_131"
down_revision: str | Sequence[str] | None = "20260908_130"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification_outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("deduplication_key", sa.String(length=200), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=128), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'processed')",
            name="ck_notification_outbox_events_status",
        ),
        sa.CheckConstraint(
            "char_length(btrim(event_type)) BETWEEN 1 AND 80",
            name="ck_notification_outbox_events_event_type_length",
        ),
        sa.CheckConstraint(
            "char_length(btrim(category)) BETWEEN 1 AND 40",
            name="ck_notification_outbox_events_category_length",
        ),
        sa.CheckConstraint(
            "char_length(btrim(deduplication_key)) BETWEEN 1 AND 200",
            name="ck_notification_outbox_events_deduplication_key_length",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "deduplication_key",
            name="uq_notification_outbox_events_user_deduplication",
        ),
    )
    op.create_index(
        "ix_notification_outbox_events_status_available_at",
        "notification_outbox_events",
        ["status", "available_at"],
        unique=False,
    )

    op.create_table(
        "notification_event_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("token_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.CheckConstraint(
            "status = 'pending'",
            name="ck_notification_event_deliveries_status",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["notification_outbox_events.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["token_id"],
            ["notification_device_tokens.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id",
            "token_id",
            name="uq_notification_event_deliveries_event_token",
        ),
    )
    op.create_index(
        "ix_notification_event_deliveries_token_id_created_at",
        "notification_event_deliveries",
        ["token_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_event_deliveries_token_id_created_at",
        table_name="notification_event_deliveries",
    )
    op.drop_table("notification_event_deliveries")
    op.drop_index(
        "ix_notification_outbox_events_status_available_at",
        table_name="notification_outbox_events",
    )
    op.drop_table("notification_outbox_events")
