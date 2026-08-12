"""link weekly plans to nutrition programs and add special meal roles"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260812_68"
down_revision: str | Sequence[str] | None = "20260812_67"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("nutrition_weekly_plans", sa.Column("program_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_nutrition_weekly_plans_program_id",
        "nutrition_weekly_plans",
        "nutrition_programs",
        ["program_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_nutrition_weekly_plans_program_id", "nutrition_weekly_plans", ["program_id"]
    )
    op.drop_constraint(
        "ck_nutrition_weekly_plan_meal_role_values",
        "nutrition_weekly_plan_meals",
        type_="check",
    )
    op.create_check_constraint(
        "ck_nutrition_weekly_plan_meal_role_values",
        "nutrition_weekly_plan_meals",
        "slot_role IN ('main_meal', 'snack', 'free_meal', 'post_workout')",
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM nutrition_weekly_plan_meals WHERE slot_role IN ('free_meal', 'post_workout')"
    )
    op.drop_constraint(
        "ck_nutrition_weekly_plan_meal_role_values",
        "nutrition_weekly_plan_meals",
        type_="check",
    )
    op.create_check_constraint(
        "ck_nutrition_weekly_plan_meal_role_values",
        "nutrition_weekly_plan_meals",
        "slot_role IN ('main_meal', 'snack')",
    )
    op.drop_index("ix_nutrition_weekly_plans_program_id", table_name="nutrition_weekly_plans")
    op.drop_constraint(
        "fk_nutrition_weekly_plans_program_id", "nutrition_weekly_plans", type_="foreignkey"
    )
    op.drop_column("nutrition_weekly_plans", "program_id")
