"""add explicit coach rejection state"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260908_129"
down_revision: str | Sequence[str] | None = "20260907_128"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_workout_plan_reviews_status_values",
        "workout_plan_reviews",
        type_="check",
    )
    op.create_check_constraint(
        "ck_workout_plan_reviews_status_values",
        "workout_plan_reviews",
        "status IN ('pending', 'claimed', 'approved', 'rejected', 'superseded')",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE workout_plan_reviews SET status = 'superseded' WHERE status = 'rejected'"
    )
    op.drop_constraint(
        "ck_workout_plan_reviews_status_values",
        "workout_plan_reviews",
        type_="check",
    )
    op.create_check_constraint(
        "ck_workout_plan_reviews_status_values",
        "workout_plan_reviews",
        "status IN ('pending', 'claimed', 'approved', 'superseded')",
    )
