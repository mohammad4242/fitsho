"""harden nutrition privacy and observability"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_50"
down_revision: str | Sequence[str] | None = "20260809_49"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("nutrition_lab_documents", sa.Column("purged_at", sa.DateTime(timezone=True)))
    op.create_unique_constraint(
        "uq_nutrition_lab_user_sha256", "nutrition_lab_documents", ["user_id", "sha256"]
    )
    op.add_column(
        "nutrition_food_photo_estimates", sa.Column("idempotency_key_hash", sa.String(64))
    )
    op.create_unique_constraint(
        "uq_nutrition_photo_user_idempotency",
        "nutrition_food_photo_estimates",
        ["user_id", "idempotency_key_hash"],
    )
    op.create_table(
        "nutrition_security_audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("owner_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(48), nullable=False),
        sa.Column("resource_id", sa.Uuid()),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("metadata_snapshot", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    for column in ("actor_user_id", "owner_user_id", "event_type", "created_at"):
        op.create_index(
            f"ix_nutrition_security_audit_events_{column}",
            "nutrition_security_audit_events",
            [column],
        )
    op.create_table(
        "nutrition_operation_rate_limits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "actor_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "actor_user_id", "operation", "window_started_at", name="uq_nutrition_rate_window"
        ),
    )
    op.create_index(
        "ix_nutrition_operation_rate_limits_actor_user_id",
        "nutrition_operation_rate_limits",
        ["actor_user_id"],
    )
    op.create_table(
        "nutrition_operational_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("category", sa.String(48), nullable=False),
        sa.Column("event_name", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("provider", sa.String(48)),
        sa.Column("counters", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("duration_ms", sa.BigInteger()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_nutrition_operational_events_category",
        "nutrition_operational_events",
        ["category"],
    )
    op.create_index(
        "ix_nutrition_operational_events_created_at",
        "nutrition_operational_events",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_table("nutrition_operational_events")
    op.drop_table("nutrition_operation_rate_limits")
    op.drop_table("nutrition_security_audit_events")
    op.drop_constraint(
        "uq_nutrition_photo_user_idempotency", "nutrition_food_photo_estimates", type_="unique"
    )
    op.drop_column("nutrition_food_photo_estimates", "idempotency_key_hash")
    op.drop_constraint("uq_nutrition_lab_user_sha256", "nutrition_lab_documents", type_="unique")
    op.drop_column("nutrition_lab_documents", "purged_at")
