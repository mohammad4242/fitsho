"""add target weight change kg per week to nutrition profiles"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260904_120"
down_revision: str | Sequence[str] | None = "20260904_119"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "nutrition_profiles",
        sa.Column("target_weight_change_kg_per_week", sa.Numeric(3, 1), nullable=True),
    )
    op.create_check_constraint(
        "ck_nutrition_profiles_target_weight_rate_range",
        "nutrition_profiles",
        "target_weight_change_kg_per_week IS NULL OR (target_weight_change_kg_per_week >= 0.3 AND target_weight_change_kg_per_week <= 2.0)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_nutrition_profiles_target_weight_rate_range",
        "nutrition_profiles",
        type_="check",
    )
    op.drop_column("nutrition_profiles", "target_weight_change_kg_per_week")
