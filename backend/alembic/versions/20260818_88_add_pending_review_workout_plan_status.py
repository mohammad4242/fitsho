"""add pending review workout plan status"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260818_88"
down_revision: str | Sequence[str] | None = "20260816_87"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STATUS_CONSTRAINT = "ck_workout_plans_status_values"
_OLD_STATUSES = "'generating', 'active', 'superseded', 'failed'"
_STATUSES = "'generating', 'pending_review', 'active', 'superseded', 'failed'"


def upgrade() -> None:
    op.drop_constraint(_STATUS_CONSTRAINT, "workout_plans", type_="check")
    op.alter_column(
        "workout_plans",
        "status",
        existing_type=sa.String(length=12),
        type_=sa.String(length=14),
        existing_nullable=False,
    )
    op.create_check_constraint(
        _STATUS_CONSTRAINT,
        "workout_plans",
        f"status IN ({_STATUSES})",
    )


def downgrade() -> None:
    op.execute("UPDATE workout_plans SET status = 'generating' WHERE status = 'pending_review'")
    op.drop_constraint(_STATUS_CONSTRAINT, "workout_plans", type_="check")
    op.alter_column(
        "workout_plans",
        "status",
        existing_type=sa.String(length=14),
        type_=sa.String(length=12),
        existing_nullable=False,
    )
    op.create_check_constraint(
        _STATUS_CONSTRAINT,
        "workout_plans",
        f"status IN ({_OLD_STATUSES})",
    )
