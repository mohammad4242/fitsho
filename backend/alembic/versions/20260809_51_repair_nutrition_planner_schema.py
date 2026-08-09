"""repair legacy nutrition planner schema drift"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_51"
down_revision: str | Sequence[str] | None = "20260809_50"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _column_names(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    food_columns = _column_names("nutrition_weekly_plan_foods")
    if "food_name_en" not in food_columns:
        op.add_column(
            "nutrition_weekly_plan_foods",
            sa.Column("food_name_en", sa.String(160), nullable=False, server_default=""),
        )
        op.execute(
            "UPDATE nutrition_weekly_plan_foods SET food_name_en = food_name_fa "
            "WHERE food_name_en = ''"
        )
        op.alter_column("nutrition_weekly_plan_foods", "food_name_en", server_default=None)

    nutrient_columns = _column_names("nutrition_weekly_plan_nutrients")
    if "difference_from_limit" not in nutrient_columns:
        op.add_column(
            "nutrition_weekly_plan_nutrients",
            sa.Column("difference_from_limit", sa.Numeric(20, 8)),
        )
    if "reason_codes" not in nutrient_columns:
        op.add_column(
            "nutrition_weekly_plan_nutrients",
            sa.Column("reason_codes", sa.JSON(), nullable=False, server_default="[]"),
        )
        op.alter_column("nutrition_weekly_plan_nutrients", "reason_codes", server_default=None)
    if "data_confidence" not in nutrient_columns:
        op.add_column(
            "nutrition_weekly_plan_nutrients",
            sa.Column("data_confidence", sa.String(16), nullable=False, server_default="low"),
        )
        op.alter_column("nutrition_weekly_plan_nutrients", "data_confidence", server_default=None)

    index_exists = op.get_bind().scalar(
        sa.text("SELECT to_regclass('public.uq_nutrition_estimate_micro_nutrient')")
    )
    if index_exists is None:
        op.create_unique_constraint(
            "uq_nutrition_estimate_micro_nutrient",
            "nutrition_estimate_micronutrient_targets",
            ["estimate_id", "nutrient_code"],
        )


def downgrade() -> None:
    # These columns and the constraint belong to the Task 12 model contract.
    # Keep repaired legacy databases compatible when Task 14 is rolled back.
    pass
