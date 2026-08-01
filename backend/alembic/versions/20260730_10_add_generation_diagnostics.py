"""add workout generation diagnostics

Revision ID: 20260730_10
Revises: 20260730_09
Create Date: 2026-07-30 23:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260730_10"
down_revision: str | Sequence[str] | None = "20260730_09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workout_plan_generations",
        sa.Column("validation_diagnostics", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workout_plan_generations", "validation_diagnostics")
