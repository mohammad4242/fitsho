"""Persist task-scoped Agent Service profile verification."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260901_115"
down_revision: str | Sequence[str] | None = "20260831_114"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_task_configs",
        sa.Column("agent_profile_id", sa.String(length=200), nullable=True),
    )
    op.create_table(
        "ai_agent_profile_verifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.String(length=200), nullable=False),
        sa.Column("task_type", sa.String(length=80), nullable=False),
        sa.Column("profile_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("safe_error_message", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "status IN ('passed', 'failed')",
            name="ck_ai_agent_profile_verifications_status_values",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id",
            "task_type",
            name="uq_ai_agent_profile_verifications_profile_task",
        ),
    )
    op.create_index(
        "ix_ai_agent_profile_verifications_profile_id",
        "ai_agent_profile_verifications",
        ["profile_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_agent_profile_verifications_profile_id",
        table_name="ai_agent_profile_verifications",
    )
    op.drop_table("ai_agent_profile_verifications")
    op.drop_column("ai_task_configs", "agent_profile_id")
