"""limit profile training days

Revision ID: bd33c3bfc1dd
Revises: 20260802_16
Create Date: 2026-08-02 14:21:36.833252

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bd33c3bfc1dd"
down_revision: str | None = "20260802_16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE user_profiles "
        "SET training_days_per_week = CASE "
        "WHEN training_days_per_week < 2 THEN 2 "
        "WHEN training_days_per_week > 5 THEN 5 "
        "ELSE training_days_per_week END"
    )
    op.drop_constraint("ck_user_profiles_training_days_range", "user_profiles", type_="check")
    op.create_check_constraint(
        "ck_user_profiles_training_days_range",
        "user_profiles",
        "training_days_per_week BETWEEN 2 AND 5",
    )


def downgrade() -> None:
    op.drop_constraint("ck_user_profiles_training_days_range", "user_profiles", type_="check")
    op.create_check_constraint(
        "ck_user_profiles_training_days_range",
        "user_profiles",
        "training_days_per_week BETWEEN 1 AND 7",
    )
