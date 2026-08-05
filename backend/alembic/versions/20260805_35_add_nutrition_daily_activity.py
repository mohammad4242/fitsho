"""add daily activity to nutrition profiles"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260805_35"
down_revision: str | Sequence[str] | None = "20260805_34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTIVITY_LEVELS = "'sedentary', 'light', 'moderate', 'very_active'"


def upgrade() -> None:
    op.add_column(
        "nutrition_profiles",
        sa.Column(
            "daily_activity_level",
            sa.String(length=16),
            nullable=False,
            server_default="moderate",
        ),
    )
    op.create_check_constraint(
        "ck_nutrition_profiles_daily_activity_level_values",
        "nutrition_profiles",
        f"daily_activity_level IN ({_ACTIVITY_LEVELS})",
    )
    op.alter_column("nutrition_profiles", "daily_activity_level", server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        "ck_nutrition_profiles_daily_activity_level_values",
        "nutrition_profiles",
        type_="check",
    )
    op.drop_column("nutrition_profiles", "daily_activity_level")
