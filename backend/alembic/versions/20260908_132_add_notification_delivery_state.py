"""add direct-provider state to notification deliveries"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260908_132"
down_revision: str | Sequence[str] | None = "20260908_131"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_notification_event_deliveries_status",
        "notification_event_deliveries",
        type_="check",
    )
    op.create_check_constraint(
        "ck_notification_event_deliveries_status",
        "notification_event_deliveries",
        "status IN ('pending', 'processing', 'sent', 'failed', 'dead_letter')",
    )
    op.add_column(
        "notification_event_deliveries",
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.add_column(
        "notification_event_deliveries",
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notification_event_deliveries",
        sa.Column("locked_by", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "notification_event_deliveries",
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notification_event_deliveries",
        sa.Column("dead_letter_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "notification_event_deliveries",
        sa.Column("last_error", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "notification_event_deliveries",
        sa.Column("provider_message_id", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "notification_event_deliveries",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_notification_event_deliveries_status_next_attempt_at",
        "notification_event_deliveries",
        ["status", "next_attempt_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_event_deliveries_status_next_attempt_at",
        table_name="notification_event_deliveries",
    )
    op.drop_column("notification_event_deliveries", "updated_at")
    op.drop_column("notification_event_deliveries", "provider_message_id")
    op.drop_column("notification_event_deliveries", "last_error")
    op.drop_column("notification_event_deliveries", "dead_letter_at")
    op.drop_column("notification_event_deliveries", "sent_at")
    op.drop_column("notification_event_deliveries", "locked_by")
    op.drop_column("notification_event_deliveries", "locked_at")
    op.drop_column("notification_event_deliveries", "next_attempt_at")
    op.drop_constraint(
        "ck_notification_event_deliveries_status",
        "notification_event_deliveries",
        type_="check",
    )
    op.create_check_constraint(
        "ck_notification_event_deliveries_status",
        "notification_event_deliveries",
        "status = 'pending'",
    )
