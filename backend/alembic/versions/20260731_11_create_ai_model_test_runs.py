"""create AI model test runs

Revision ID: 20260731_11
Revises: 20260730_10
Create Date: 2026-07-31 14:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_11"
down_revision: str | Sequence[str] | None = "20260730_10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_model_test_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ai_model_id", sa.Uuid(), nullable=False),
        sa.Column("model_id", sa.String(length=160), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("error_code", sa.String(length=80)),
        sa.Column("safe_error_message", sa.String(length=500)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "outcome IN ('succeeded', 'failed')",
            name="ck_ai_model_test_runs_outcome_values",
        ),
        sa.ForeignKeyConstraint(["ai_model_id"], ["ai_models.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_model_test_runs_created_at", "ai_model_test_runs", ["created_at"])
    op.create_index(
        "ix_ai_model_test_runs_model_created_at",
        "ai_model_test_runs",
        ["ai_model_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_model_test_runs_model_created_at", table_name="ai_model_test_runs")
    op.drop_index("ix_ai_model_test_runs_created_at", table_name="ai_model_test_runs")
    op.drop_table("ai_model_test_runs")
