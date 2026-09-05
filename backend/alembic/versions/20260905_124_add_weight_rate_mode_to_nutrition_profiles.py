"""add weight_rate_mode to nutrition profiles"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260905_124"
down_revision: str | Sequence[str] | None = "20260905_123"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "nutrition_profiles",
        sa.Column("weight_rate_mode", sa.String(length=32), nullable=False, server_default="safe"),
    )
    op.create_check_constraint(
        "ck_nutrition_profiles_weight_rate_mode_values",
        "nutrition_profiles",
        "weight_rate_mode IN ('safe', 'user_override')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_nutrition_profiles_weight_rate_mode_values",
        "nutrition_profiles",
        type_="check",
    )
    op.drop_column("nutrition_profiles", "weight_rate_mode")
