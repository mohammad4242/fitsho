"""Set the default AI request timeout to seven minutes."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260903_118"
down_revision: str | Sequence[str] | None = "20260902_117"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "ai_task_configs",
        "timeout_seconds",
        existing_type=sa.Integer(),
        server_default="420",
        existing_nullable=False,
    )
    op.execute(sa.text("UPDATE ai_task_configs SET timeout_seconds = 420"))


def downgrade() -> None:
    op.alter_column(
        "ai_task_configs",
        "timeout_seconds",
        existing_type=sa.Integer(),
        server_default="45",
        existing_nullable=False,
    )
