"""link end-of-cycle feedback to body progress evidence"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260818_96"
down_revision: str | Sequence[str] | None = "20260818_95"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workout_cycle_feedback",
        sa.Column("body_progress_comparison_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_workout_cycle_feedback_body_progress_comparison_id",
        "workout_cycle_feedback",
        ["body_progress_comparison_id"],
    )
    op.create_foreign_key(
        "fk_workout_cycle_feedback_body_progress_comparison",
        "workout_cycle_feedback",
        "workout_cycle_body_progress_comparisons",
        ["body_progress_comparison_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_workout_cycle_feedback_body_progress_comparison",
        "workout_cycle_feedback",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_workout_cycle_feedback_body_progress_comparison_id",
        table_name="workout_cycle_feedback",
    )
    op.drop_column("workout_cycle_feedback", "body_progress_comparison_id")
