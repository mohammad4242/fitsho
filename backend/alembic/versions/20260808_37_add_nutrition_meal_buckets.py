"""add typed nutrition meal-structure buckets"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_37"
down_revision: str | Sequence[str] | None = "20260805_36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "nutrition_profiles",
        sa.Column("main_meal_count_bucket", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "nutrition_profiles",
        sa.Column("snack_count_bucket", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "nutrition_profiles",
        sa.Column("effective_main_meal_slots", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "nutrition_profiles",
        sa.Column("effective_snack_slots", sa.SmallInteger(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE nutrition_profiles SET "
            "main_meal_count_bucket = CASE WHEN meals_per_day <= 2 THEN 'two_main_meals' "
            "WHEN meals_per_day = 3 THEN 'three_main_meals' ELSE 'four_or_more_main_meals' END, "
            "snack_count_bucket = CASE WHEN snacks_per_day <= 0 THEN 'zero_snacks' "
            "WHEN snacks_per_day = 1 THEN 'one_snack' WHEN snacks_per_day = 2 THEN 'two_snacks' "
            "ELSE 'three_or_more_snacks' END, "
            "effective_main_meal_slots = CASE WHEN meals_per_day <= 2 THEN 2 "
            "WHEN meals_per_day = 3 THEN 3 ELSE 4 END, "
            "effective_snack_slots = CASE WHEN snacks_per_day <= 0 THEN 0 "
            "WHEN snacks_per_day = 1 THEN 1 WHEN snacks_per_day = 2 THEN 2 ELSE 3 END"
        )
    )
    op.alter_column("nutrition_profiles", "main_meal_count_bucket", nullable=False)
    op.alter_column("nutrition_profiles", "snack_count_bucket", nullable=False)
    op.alter_column("nutrition_profiles", "effective_main_meal_slots", nullable=False)
    op.alter_column("nutrition_profiles", "effective_snack_slots", nullable=False)
    op.create_check_constraint(
        "ck_nutrition_profiles_main_meal_bucket_values",
        "nutrition_profiles",
        "main_meal_count_bucket IN "
        "('two_main_meals', 'three_main_meals', 'four_or_more_main_meals')",
    )
    op.create_check_constraint(
        "ck_nutrition_profiles_snack_bucket_values",
        "nutrition_profiles",
        "snack_count_bucket IN ('zero_snacks', 'one_snack', 'two_snacks', 'three_or_more_snacks')",
    )
    op.create_check_constraint(
        "ck_nutrition_profiles_effective_main_meal_slots",
        "nutrition_profiles",
        "effective_main_meal_slots BETWEEN 2 AND 4",
    )
    op.create_check_constraint(
        "ck_nutrition_profiles_effective_snack_slots",
        "nutrition_profiles",
        "effective_snack_slots BETWEEN 0 AND 3",
    )


def downgrade() -> None:
    op.drop_constraint("ck_nutrition_profiles_effective_snack_slots", "nutrition_profiles")
    op.drop_constraint("ck_nutrition_profiles_effective_main_meal_slots", "nutrition_profiles")
    op.drop_constraint("ck_nutrition_profiles_snack_bucket_values", "nutrition_profiles")
    op.drop_constraint("ck_nutrition_profiles_main_meal_bucket_values", "nutrition_profiles")
    op.drop_column("nutrition_profiles", "effective_snack_slots")
    op.drop_column("nutrition_profiles", "effective_main_meal_slots")
    op.drop_column("nutrition_profiles", "snack_count_bucket")
    op.drop_column("nutrition_profiles", "main_meal_count_bucket")
