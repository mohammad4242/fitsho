"""add product mode to unified profiles"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "20260805_30"
down_revision: str | Sequence[str] | None = "20260803_29"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("product_mode", sa.String(length=16), nullable=True))
    op.execute("UPDATE user_profiles SET product_mode = 'training' WHERE product_mode IS NULL")
    op.alter_column("user_profiles", "product_mode", nullable=False)
    op.create_check_constraint(
        "ck_user_profiles_product_mode_values",
        "user_profiles",
        "product_mode IN ('training', 'nutrition', 'both')",
    )
    for column in (
        "display_name",
        "birth_date",
        "sex",
        "height_cm",
        "fitness_goal",
        "experience_level",
        "training_days_per_week",
        "training_location",
        "session_duration_minutes",
        "plan_duration_weeks",
        "workout_generation_method",
    ):
        op.alter_column("user_profiles", column, nullable=True)
    op.alter_column("user_profiles", "plan_duration_weeks", server_default=None)
    op.alter_column("user_profiles", "workout_generation_method", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_user_profiles_product_mode_values", "user_profiles")
    op.drop_column("user_profiles", "product_mode")
