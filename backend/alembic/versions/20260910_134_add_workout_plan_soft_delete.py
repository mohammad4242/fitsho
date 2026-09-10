"""add workout plan soft delete"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260910_134"
down_revision: str | Sequence[str] | None = "20260908_133"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workout_plans",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workout_plans", "deleted_at")
