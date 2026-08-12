"""add nutrition program catalogue"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260812_64"
down_revision: str | Sequence[str] | None = "20260811_63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DIET_STYLES = (
    "economy",
    "balanced_iranian",
    "high_protein_gym",
    "quick_easy",
    "premium_varied",
)
MEAL_CATEGORIES = ("breakfast", "lunch", "post_workout", "snack", "dinner")


def upgrade() -> None:
    op.create_table(
        "nutrition_programs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name_fa", sa.String(length=160), nullable=False),
        sa.Column("name_en", sa.String(length=160), nullable=False),
        sa.Column("description_fa", sa.String(length=1000), nullable=False),
        sa.Column("description_en", sa.String(length=1000), nullable=False),
        sa.Column("diet_style", sa.String(length=20), nullable=False),
        sa.Column("post_workout_enabled", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            f"diet_style IN ({', '.join(repr(value) for value in DIET_STYLES)})",
            name="ck_nutrition_programs_diet_style_values",
        ),
        sa.CheckConstraint(
            "slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_nutrition_programs_slug_format"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_nutrition_programs_slug"),
    )
    op.create_index("ix_nutrition_programs_diet_style", "nutrition_programs", ["diet_style"])
    op.create_table(
        "nutrition_program_days",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("program_id", sa.Uuid(), nullable=False),
        sa.Column("day_number", sa.SmallInteger(), nullable=False),
        sa.Column("post_workout_enabled", sa.Boolean(), nullable=False),
        sa.CheckConstraint("day_number BETWEEN 1 AND 7", name="ck_nutrition_program_days_number"),
        sa.ForeignKeyConstraint(["program_id"], ["nutrition_programs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("program_id", "day_number", name="uq_nutrition_program_days_number"),
    )
    op.create_index(
        "ix_nutrition_program_days_program_id", "nutrition_program_days", ["program_id"]
    )
    op.create_table(
        "nutrition_program_slots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("program_day_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(length=12), nullable=False),
        sa.Column("meal_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            f"category IN ({', '.join(repr(value) for value in MEAL_CATEGORIES)})",
            name="ck_nutrition_program_slots_category_values",
        ),
        sa.ForeignKeyConstraint(["meal_id"], ["nutrition_catalogue_meals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["program_day_id"], ["nutrition_program_days.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "program_day_id", "category", name="uq_nutrition_program_slots_category"
        ),
    )
    op.create_index(
        "ix_nutrition_program_slots_program_day_id",
        "nutrition_program_slots",
        ["program_day_id"],
    )
    op.create_index("ix_nutrition_program_slots_meal_id", "nutrition_program_slots", ["meal_id"])


def downgrade() -> None:
    op.drop_index("ix_nutrition_program_slots_meal_id", table_name="nutrition_program_slots")
    op.drop_index("ix_nutrition_program_slots_program_day_id", table_name="nutrition_program_slots")
    op.drop_table("nutrition_program_slots")
    op.drop_index("ix_nutrition_program_days_program_id", table_name="nutrition_program_days")
    op.drop_table("nutrition_program_days")
    op.drop_index("ix_nutrition_programs_diet_style", table_name="nutrition_programs")
    op.drop_table("nutrition_programs")
