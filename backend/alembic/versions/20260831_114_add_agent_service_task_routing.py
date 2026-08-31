"""Add agent-service routing fields to AI task configs."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260831_114"
down_revision: str | Sequence[str] | None = "20260831_113"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_task_configs",
        sa.Column(
            "execution_backend",
            sa.String(length=32),
            server_default="api",
            nullable=False,
        ),
    )
    op.add_column(
        "ai_task_configs",
        sa.Column("agent_name", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "ai_task_configs",
        sa.Column("agent_model_id", sa.String(length=300), nullable=True),
    )
    op.create_check_constraint(
        "ck_ai_task_configs_execution_backend_values",
        "ai_task_configs",
        "execution_backend IN ('api', 'agent_service')",
    )
    op.create_check_constraint(
        "ck_ai_task_configs_agent_name_values",
        "ai_task_configs",
        "agent_name IS NULL OR agent_name IN ('antigravity', 'codex', 'claude')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_ai_task_configs_agent_name_values", "ai_task_configs", type_="check"
    )
    op.drop_constraint(
        "ck_ai_task_configs_execution_backend_values", "ai_task_configs", type_="check"
    )
    op.drop_column("ai_task_configs", "agent_model_id")
    op.drop_column("ai_task_configs", "agent_name")
    op.drop_column("ai_task_configs", "execution_backend")
