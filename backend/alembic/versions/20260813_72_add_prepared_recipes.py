"""add immutable Prepared Recipe revisions"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260813_72"
down_revision: str | Sequence[str] | None = "20260813_71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "nutrition_catalogue_meals",
        sa.Column("calculation_mode", sa.String(32), nullable=False, server_default="simple"),
    )
    op.create_check_constraint(
        "ck_nutrition_catalogue_meal_calculation_mode_values",
        "nutrition_catalogue_meals",
        "calculation_mode IN ('simple', 'prepared_recipe')",
    )
    op.create_table(
        "nutrition_prepared_recipes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "meal_id",
            sa.Uuid(),
            sa.ForeignKey("nutrition_catalogue_meals.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
    )
    op.create_index(
        "ix_nutrition_prepared_recipes_meal_id",
        "nutrition_prepared_recipes",
        ["meal_id"],
        unique=True,
    )
    op.create_table(
        "nutrition_prepared_recipe_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "recipe_id",
            sa.Uuid(),
            sa.ForeignKey("nutrition_prepared_recipes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("verification_status", sa.String(16), nullable=False),
        sa.Column("calculation_version", sa.String(64), nullable=False),
        sa.Column("source_name", sa.String(160), nullable=False),
        sa.Column("source_reference", sa.String(500), nullable=False),
        sa.Column("notes", sa.String(1000)),
        sa.Column("yield_method", sa.String(64), nullable=False),
        sa.Column("reference_input_grams", sa.Numeric(20, 8), nullable=False),
        sa.Column("final_cooked_yield_grams", sa.Numeric(20, 8), nullable=False),
        sa.Column("yield_source_name", sa.String(160), nullable=False),
        sa.Column("yield_source_reference", sa.String(500), nullable=False),
        sa.Column("yield_notes", sa.String(1000)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("version > 0", name="ck_nutrition_prepared_recipe_version_positive"),
        sa.CheckConstraint(
            "verification_status IN ('draft', 'verified', 'retired')",
            name="ck_nutrition_prepared_recipe_status_values",
        ),
        sa.CheckConstraint(
            "reference_input_grams > 0 AND final_cooked_yield_grams > 0",
            name="ck_nutrition_prepared_recipe_yield_positive",
        ),
        sa.UniqueConstraint("recipe_id", "version", name="uq_nutrition_prepared_recipe_version"),
    )
    op.create_index(
        "ix_nutrition_prepared_recipe_revisions_recipe_id",
        "nutrition_prepared_recipe_revisions",
        ["recipe_id"],
    )
    op.create_table(
        "nutrition_prepared_recipe_ingredients",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "revision_id",
            sa.Uuid(),
            sa.ForeignKey("nutrition_prepared_recipe_revisions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "food_id",
            sa.Uuid(),
            sa.ForeignKey("nutrition_catalogue_foods.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("reference_grams", sa.Numeric(20, 8), nullable=False),
        sa.Column("min_grams", sa.Numeric(20, 8), nullable=False),
        sa.Column("max_grams", sa.Numeric(20, 8), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "min_grams >= 0 AND min_grams <= reference_grams AND reference_grams <= max_grams",
            name="ck_nutrition_recipe_ingredient_bounds",
        ),
        sa.CheckConstraint(
            "NOT is_required OR (min_grams > 0 AND reference_grams > 0 AND max_grams > 0)",
            name="ck_nutrition_recipe_required_positive",
        ),
        sa.UniqueConstraint("revision_id", "food_id", name="uq_nutrition_recipe_ingredient_food"),
    )
    op.create_index(
        "ix_nutrition_prepared_recipe_ingredients_revision_id",
        "nutrition_prepared_recipe_ingredients",
        ["revision_id"],
    )
    op.create_table(
        "nutrition_prepared_recipe_ratios",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "revision_id",
            sa.Uuid(),
            sa.ForeignKey("nutrition_prepared_recipe_revisions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "numerator_food_id",
            sa.Uuid(),
            sa.ForeignKey("nutrition_catalogue_foods.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "denominator_food_id",
            sa.Uuid(),
            sa.ForeignKey("nutrition_catalogue_foods.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("min_ratio", sa.Numeric(20, 8), nullable=False),
        sa.Column("max_ratio", sa.Numeric(20, 8), nullable=False),
        sa.CheckConstraint(
            "numerator_food_id <> denominator_food_id",
            name="ck_nutrition_recipe_ratio_distinct",
        ),
        sa.CheckConstraint(
            "min_ratio > 0 AND min_ratio <= max_ratio",
            name="ck_nutrition_recipe_ratio_bounds",
        ),
        sa.UniqueConstraint(
            "revision_id",
            "numerator_food_id",
            "denominator_food_id",
            name="uq_nutrition_recipe_ratio_pair",
        ),
    )
    op.create_index(
        "ix_nutrition_prepared_recipe_ratios_revision_id",
        "nutrition_prepared_recipe_ratios",
        ["revision_id"],
    )
    op.create_table(
        "nutrition_prepared_recipe_data_gaps",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "revision_id",
            sa.Uuid(),
            sa.ForeignKey("nutrition_prepared_recipe_revisions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ingredient_name_fa", sa.String(160), nullable=False),
        sa.Column("ingredient_name_en", sa.String(160), nullable=False),
        sa.Column("message_fa", sa.String(500), nullable=False),
        sa.Column("message_en", sa.String(500), nullable=False),
    )
    op.create_index(
        "ix_nutrition_prepared_recipe_data_gaps_revision_id",
        "nutrition_prepared_recipe_data_gaps",
        ["revision_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_nutrition_prepared_recipe_data_gaps_revision_id",
        table_name="nutrition_prepared_recipe_data_gaps",
    )
    op.drop_table("nutrition_prepared_recipe_data_gaps")
    op.drop_index(
        "ix_nutrition_prepared_recipe_ratios_revision_id",
        table_name="nutrition_prepared_recipe_ratios",
    )
    op.drop_table("nutrition_prepared_recipe_ratios")
    op.drop_index(
        "ix_nutrition_prepared_recipe_ingredients_revision_id",
        table_name="nutrition_prepared_recipe_ingredients",
    )
    op.drop_table("nutrition_prepared_recipe_ingredients")
    op.drop_index(
        "ix_nutrition_prepared_recipe_revisions_recipe_id",
        table_name="nutrition_prepared_recipe_revisions",
    )
    op.drop_table("nutrition_prepared_recipe_revisions")
    op.drop_index("ix_nutrition_prepared_recipes_meal_id", table_name="nutrition_prepared_recipes")
    op.drop_table("nutrition_prepared_recipes")
    op.drop_constraint(
        "ck_nutrition_catalogue_meal_calculation_mode_values",
        "nutrition_catalogue_meals",
        type_="check",
    )
    op.drop_column("nutrition_catalogue_meals", "calculation_mode")
