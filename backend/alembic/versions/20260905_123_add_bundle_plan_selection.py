"""add bundle plan selection columns"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260905_123"
down_revision: str | Sequence[str] | None = "20260904_122"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "nutrition_plan_bundles",
        sa.Column("selected_plan_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "nutrition_plan_bundles",
        sa.Column("selected_plan_role", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "nutrition_plan_bundles",
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_nutrition_plan_bundles_selected_plan_id",
        "nutrition_plan_bundles",
        "nutrition_weekly_plans",
        ["selected_plan_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_nutrition_plan_bundles_selected_plan_id",
        "nutrition_plan_bundles",
        ["selected_plan_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_nutrition_plan_bundles_selected_plan_id",
        table_name="nutrition_plan_bundles",
    )
    op.drop_constraint(
        "fk_nutrition_plan_bundles_selected_plan_id",
        "nutrition_plan_bundles",
        type_="foreignkey",
    )
    op.drop_column("nutrition_plan_bundles", "selected_at")
    op.drop_column("nutrition_plan_bundles", "selected_plan_role")
    op.drop_column("nutrition_plan_bundles", "selected_plan_id")
