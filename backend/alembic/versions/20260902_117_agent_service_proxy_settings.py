"""Persist the admin-managed Agent Service proxy selection."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260902_117"
down_revision: str | Sequence[str] | None = "20260901_116"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_agent_service_proxy_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "source",
            sa.String(length=32),
            server_default="deployment_default",
            nullable=False,
        ),
        sa.Column("encrypted_proxy_url", sa.String(length=2048), nullable=True),
        sa.Column("masked_proxy_url", sa.String(length=500), nullable=True),
        sa.Column("last_applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_apply_error", sa.String(length=500), nullable=True),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_ai_agent_service_proxy_settings_singleton"),
        sa.CheckConstraint(
            "source IN ('deployment_default', 'custom')",
            name="ck_ai_agent_service_proxy_settings_source_values",
        ),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("ai_agent_service_proxy_settings")
