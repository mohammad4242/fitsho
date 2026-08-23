"""add workout exercise superset groups"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260823_105"
down_revision: str | Sequence[str] | None = "20260821_104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workout_plan_exercises",
        sa.Column("superset_group", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workout_plan_exercises", "superset_group")
