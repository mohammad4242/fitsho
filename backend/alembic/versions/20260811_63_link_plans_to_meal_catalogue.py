"""link generated nutrition plan meals to catalogue templates"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260811_63"
down_revision: str | Sequence[str] | None = "20260811_62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "nutrition_weekly_plan_meals",
        sa.Column("catalogue_meal_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "nutrition_weekly_plan_meals",
        sa.Column("catalogue_meal_category", sa.String(length=32), nullable=True),
    )
    op.create_foreign_key(
        "fk_nutrition_weekly_plan_meals_catalogue_meal_id",
        "nutrition_weekly_plan_meals",
        "nutrition_catalogue_meals",
        ["catalogue_meal_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_nutrition_weekly_plan_meals_catalogue_meal_id",
        "nutrition_weekly_plan_meals",
        ["catalogue_meal_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_nutrition_weekly_plan_meals_catalogue_meal_id",
        table_name="nutrition_weekly_plan_meals",
    )
    op.drop_constraint(
        "fk_nutrition_weekly_plan_meals_catalogue_meal_id",
        "nutrition_weekly_plan_meals",
        type_="foreignkey",
    )
    op.drop_column("nutrition_weekly_plan_meals", "catalogue_meal_category")
    op.drop_column("nutrition_weekly_plan_meals", "catalogue_meal_id")
