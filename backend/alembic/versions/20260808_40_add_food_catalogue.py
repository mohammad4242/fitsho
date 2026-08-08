"""add verified nutrition food catalogue and structured meals"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_40"
down_revision: str | Sequence[str] | None = "20260808_39"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "nutrition_catalogue_foods",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(length=120), nullable=False, unique=True),
        sa.Column("name_fa", sa.String(length=160), nullable=False),
        sa.Column("name_en", sa.String(length=160), nullable=False),
        sa.Column("verification_status", sa.String(length=16), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("source_reference", sa.String(length=500), nullable=False),
        sa.Column("source_food_id", sa.String(length=120)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "verification_status IN ('draft', 'verified', 'retired')",
            name="ck_nutrition_catalogue_food_status_values",
        ),
    )
    op.create_table(
        "nutrition_catalogue_food_roles",
        sa.Column("food_id", sa.Uuid(), primary_key=True),
        sa.Column("role", sa.String(length=24), primary_key=True),
        sa.ForeignKeyConstraint(["food_id"], ["nutrition_catalogue_foods.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "role IN ('main_protein', 'main_staple', 'snack', 'flexible')",
            name="ck_nutrition_catalogue_food_roles_values",
        ),
    )
    op.create_table(
        "nutrition_food_compositions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("food_id", sa.Uuid(), nullable=False),
        sa.Column("nutrient_code", sa.String(length=48), nullable=False),
        sa.Column("value_per_100g", sa.Numeric(20, 8), nullable=False),
        sa.Column("unit", sa.String(length=24), nullable=False),
        sa.Column("unit_form", sa.String(length=48), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("source_reference", sa.String(length=500), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["food_id"], ["nutrition_catalogue_foods.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("food_id", "nutrient_code", name="uq_nutrition_food_composition"),
        sa.CheckConstraint("value_per_100g >= 0", name="ck_nutrition_food_composition_nonnegative"),
        sa.CheckConstraint(
            "confidence IN ('high', 'medium', 'low')",
            name="ck_nutrition_food_composition_confidence_values",
        ),
    )
    op.create_index(
        "ix_nutrition_food_compositions_food_id", "nutrition_food_compositions", ["food_id"]
    )
    op.create_table(
        "nutrition_catalogue_meals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name_fa", sa.String(length=160), nullable=False),
        sa.Column("name_en", sa.String(length=160), nullable=False),
        sa.Column("slot_role", sa.String(length=16), nullable=False),
        sa.Column("verification_status", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "slot_role IN ('main_meal', 'snack')", name="ck_nutrition_catalogue_meal_slot_values"
        ),
        sa.CheckConstraint(
            "verification_status IN ('draft', 'verified', 'retired')",
            name="ck_nutrition_catalogue_meal_status_values",
        ),
    )
    op.create_table(
        "nutrition_catalogue_meal_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("meal_id", sa.Uuid(), nullable=False),
        sa.Column("food_id", sa.Uuid(), nullable=False),
        sa.Column("grams", sa.Numeric(20, 8), nullable=False),
        sa.ForeignKeyConstraint(["meal_id"], ["nutrition_catalogue_meals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["food_id"], ["nutrition_catalogue_foods.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("grams > 0", name="ck_nutrition_catalogue_meal_item_grams_positive"),
    )
    op.create_index(
        "ix_nutrition_catalogue_meal_items_meal_id", "nutrition_catalogue_meal_items", ["meal_id"]
    )
    foods = sa.table(
        "nutrition_catalogue_foods",
        sa.column("id", sa.Uuid),
        sa.column("slug", sa.String),
        sa.column("name_fa", sa.String),
        sa.column("name_en", sa.String),
        sa.column("verification_status", sa.String),
        sa.column("source_name", sa.String),
        sa.column("source_reference", sa.String),
    )
    source_name = "USDA FoodData Central verified mapping"
    source_reference = "https://fdc.nal.usda.gov/"
    food_rows = [
        {
            "id": UUID("2e4a3d5d-669a-4b36-b7aa-4f9cb5edcf01"),
            "slug": "cooked-basmati-rice",
            "name_fa": "برنج باسماتی پخته",
            "name_en": "Cooked basmati rice",
        },
        {
            "id": UUID("2e4a3d5d-669a-4b36-b7aa-4f9cb5edcf02"),
            "slug": "grilled-chicken-breast",
            "name_fa": "سینه مرغ گریل‌شده",
            "name_en": "Grilled chicken breast",
        },
        {
            "id": UUID("2e4a3d5d-669a-4b36-b7aa-4f9cb5edcf03"),
            "slug": "plain-yogurt",
            "name_fa": "ماست ساده",
            "name_en": "Plain yogurt",
        },
    ]
    op.bulk_insert(
        foods,
        [
            {
                **row,
                "verification_status": "verified",
                "source_name": source_name,
                "source_reference": source_reference,
            }
            for row in food_rows
        ],
    )
    roles = sa.table(
        "nutrition_catalogue_food_roles",
        sa.column("food_id", sa.Uuid),
        sa.column("role", sa.String),
    )
    op.bulk_insert(
        roles,
        [
            {"food_id": food_rows[0]["id"], "role": "main_staple"},
            {"food_id": food_rows[1]["id"], "role": "main_protein"},
            {"food_id": food_rows[2]["id"], "role": "snack"},
            {"food_id": food_rows[2]["id"], "role": "flexible"},
        ],
    )
    composition = sa.table(
        "nutrition_food_compositions",
        sa.column("id", sa.Uuid),
        sa.column("food_id", sa.Uuid),
        sa.column("nutrient_code", sa.String),
        sa.column("value_per_100g", sa.Numeric),
        sa.column("unit", sa.String),
        sa.column("unit_form", sa.String),
        sa.column("source_name", sa.String),
        sa.column("source_reference", sa.String),
        sa.column("confidence", sa.String),
    )
    composition_rows = [
        (food_rows[0]["id"], "energy_kcal", 121, "kcal"),
        (food_rows[0]["id"], "protein_g", 2.5, "g"),
        (food_rows[1]["id"], "energy_kcal", 165, "kcal"),
        (food_rows[1]["id"], "protein_g", 31, "g"),
        (food_rows[2]["id"], "energy_kcal", 61, "kcal"),
        (food_rows[2]["id"], "calcium_mg", 121, "mg"),
    ]
    op.bulk_insert(
        composition,
        [
            {
                "id": UUID(f"2e4a3d5d-669a-4b36-b7aa-4f9cb5edcf{index:02d}"),
                "food_id": food_id,
                "nutrient_code": nutrient_code,
                "value_per_100g": value,
                "unit": unit,
                "unit_form": "nutrient_mass",
                "source_name": source_name,
                "source_reference": source_reference,
                "confidence": "high",
            }
            for index, (food_id, nutrient_code, value, unit) in enumerate(
                composition_rows, start=10
            )
        ],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_nutrition_catalogue_meal_items_meal_id", table_name="nutrition_catalogue_meal_items"
    )
    op.drop_table("nutrition_catalogue_meal_items")
    op.drop_table("nutrition_catalogue_meals")
    op.drop_index(
        "ix_nutrition_food_compositions_food_id", table_name="nutrition_food_compositions"
    )
    op.drop_table("nutrition_food_compositions")
    op.drop_table("nutrition_catalogue_food_roles")
    op.drop_table("nutrition_catalogue_foods")
