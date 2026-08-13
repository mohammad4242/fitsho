"""add Prepared Recipe weekly-plan output snapshots"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260813_73"
down_revision: str | Sequence[str] | None = "20260813_72"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("nutrition_weekly_plan_foods", "food_id", nullable=True)
    op.add_column(
        "nutrition_weekly_plan_foods",
        sa.Column("item_kind", sa.String(32), nullable=False, server_default="food"),
    )
    op.add_column(
        "nutrition_weekly_plan_foods", sa.Column("recipe_snapshot", sa.JSON(), nullable=True)
    )
    op.create_check_constraint(
        "ck_nutrition_weekly_plan_food_item_kind_values",
        "nutrition_weekly_plan_foods",
        "item_kind IN ('food', 'prepared_recipe')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_nutrition_weekly_plan_food_item_kind_values",
        "nutrition_weekly_plan_foods",
        type_="check",
    )
    op.drop_column("nutrition_weekly_plan_foods", "recipe_snapshot")
    op.drop_column("nutrition_weekly_plan_foods", "item_kind")
    op.alter_column("nutrition_weekly_plan_foods", "food_id", nullable=False)
