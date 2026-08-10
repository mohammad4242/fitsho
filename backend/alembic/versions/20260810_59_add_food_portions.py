"""add source-backed household display portions to nutrition foods"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa

from alembic import op

revision: str = "20260810_59"
down_revision: str | Sequence[str] | None = "20260809_58"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "nutrition_food_portions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("food_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 4), nullable=False, server_default="1"),
        sa.Column("label_fa", sa.String(80), nullable=False),
        sa.Column("label_en", sa.String(80), nullable=False),
        sa.Column("grams", sa.Numeric(12, 4), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_name", sa.String(160), nullable=False),
        sa.Column("source_reference", sa.String(500), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_nutrition_food_portion_quantity_positive"),
        sa.CheckConstraint("grams > 0", name="ck_nutrition_food_portion_grams_positive"),
        sa.CheckConstraint(
            "code IN ('piece', 'palm', 'cup', 'tablespoon', 'teaspoon')",
            name="ck_nutrition_food_portion_code_values",
        ),
        sa.ForeignKeyConstraint(["food_id"], ["nutrition_catalogue_foods.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("food_id", "code", name="uq_nutrition_food_portion_code"),
    )
    op.create_index("ix_nutrition_food_portions_food_id", "nutrition_food_portions", ["food_id"])
    foods = sa.table(
        "nutrition_catalogue_foods", sa.column("id", sa.Uuid()), sa.column("slug", sa.String())
    )
    portions = sa.table(
        "nutrition_food_portions",
        sa.column("id", sa.Uuid()),
        sa.column("food_id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("quantity", sa.Numeric()),
        sa.column("label_fa", sa.String()),
        sa.column("label_en", sa.String()),
        sa.column("grams", sa.Numeric()),
        sa.column("is_default", sa.Boolean()),
        sa.column("sort_order", sa.Integer()),
        sa.column("source_name", sa.String()),
        sa.column("source_reference", sa.String()),
    )
    egg_id = op.get_bind().scalar(sa.select(foods.c.id).where(foods.c.slug == "egg"))
    if egg_id is not None:
        op.get_bind().execute(
            portions.insert().values(
                id=uuid5(NAMESPACE_URL, "fitsho:nutrition:food:egg:portion:piece"),
                food_id=egg_id,
                code="piece",
                quantity=1,
                label_fa="۱ عدد",
                label_en="1 piece",
                grams=50,
                is_default=True,
                sort_order=0,
                source_name="USDA FoodData Central SR Legacy",
                source_reference="https://fdc.nal.usda.gov/download-datasets/",
            )
        )


def downgrade() -> None:
    op.drop_index("ix_nutrition_food_portions_food_id", table_name="nutrition_food_portions")
    op.drop_table("nutrition_food_portions")
