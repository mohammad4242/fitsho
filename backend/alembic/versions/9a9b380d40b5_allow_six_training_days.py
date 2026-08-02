"""allow six training days

Revision ID: 9a9b380d40b5
Revises: bd33c3bfc1dd
Create Date: 2026-08-02 14:37:03.820386

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9a9b380d40b5"
down_revision: str | None = "bd33c3bfc1dd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_user_profiles_training_days_range", "user_profiles", type_="check")
    op.create_check_constraint(
        "ck_user_profiles_training_days_range",
        "user_profiles",
        "training_days_per_week BETWEEN 2 AND 6",
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_profiles_training_days_range", "user_profiles", type_="check")
    op.create_check_constraint(
        "ck_user_profiles_training_days_range",
        "user_profiles",
        "training_days_per_week BETWEEN 2 AND 5",
    )
