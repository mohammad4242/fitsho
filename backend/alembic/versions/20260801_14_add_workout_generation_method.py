"""add workout generation method preference"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260801_14"
down_revision = "20260731_13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column(
            "workout_generation_method",
            sa.String(length=20),
            server_default="fitsho_coach",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_user_profiles_workout_generation_method_values",
        "user_profiles",
        "workout_generation_method IN ('fitsho_coach', 'ai')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_user_profiles_workout_generation_method_values",
        "user_profiles",
        type_="check",
    )
    op.drop_column("user_profiles", "workout_generation_method")
