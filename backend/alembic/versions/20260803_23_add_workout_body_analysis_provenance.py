"""persist body-analysis provenance on workout plans"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_23"
down_revision: str | Sequence[str] | None = "20260803_22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workout_plans",
        sa.Column(
            "body_analysis_provenance",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("workout_plans", "body_analysis_provenance")
