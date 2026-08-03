"""persist AI coach template choice and explanations"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_24"
down_revision: str | Sequence[str] | None = "20260803_23"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workout_plans", sa.Column("ai_coach_template_slug", sa.String(120)))
    op.add_column("workout_plans", sa.Column("ai_coach_program_explanation_fa", sa.Text()))
    op.add_column("workout_days", sa.Column("ai_coach_explanation_fa", sa.Text()))


def downgrade() -> None:
    op.drop_column("workout_days", "ai_coach_explanation_fa")
    op.drop_column("workout_plans", "ai_coach_program_explanation_fa")
    op.drop_column("workout_plans", "ai_coach_template_slug")
