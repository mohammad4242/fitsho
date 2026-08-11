"""evolve nutrition meals into bounded catalogue templates"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa

from alembic import op

revision: str = "20260811_62"
down_revision: str | Sequence[str] | None = "20260811_61"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIES = ("breakfast", "lunch", "post_workout", "snack", "dinner")
ROLES = ("protein", "carbohydrate", "fat", "fibre", "micronutrient_source")
SEEDS = (
    (
        "breakfast",
        "تخم‌مرغ نیمرو با نان و گوجه خردشده",
        "Fried eggs with bread and chopped tomato",
        (
            ("egg", 100, 50, 200, True, "protein"),
            ("sangak-bread", 60, 30, 120, True, "carbohydrate"),
            ("tomato", 80, 30, 150, False, "micronutrient_source"),
            ("vegetable-oil", 5, 2, 10, False, "fat"),
        ),
    ),
    (
        "lunch",
        "گوشت گوسفند و برنج با سالاد شیرازی",
        "Lamb and rice with Shirazi salad",
        (
            ("lamb", 150, 80, 220, True, "protein"),
            ("basmati-rice", 80, 50, 130, True, "carbohydrate"),
            ("tomato", 60, 30, 120, True, "micronutrient_source"),
            ("cucumber", 60, 30, 120, True, "fibre"),
            ("onion", 20, 10, 40, False, "micronutrient_source"),
        ),
    ),
    (
        "post_workout",
        "تخم‌مرغ آب‌پز و سیب‌زمینی تنوری",
        "Boiled eggs with baked potato",
        (("egg", 100, 50, 200, True, "protein"), ("potato", 250, 150, 400, True, "carbohydrate")),
    ),
    (
        "snack",
        "۵۰ گرم بادام‌زمینی",
        "50 g peanuts",
        (("peanuts", 50, 20, 80, True, "fat"),),
    ),
    (
        "dinner",
        "سینه مرغ و برنج با سبزیجات",
        "Chicken breast and rice with vegetables",
        (
            ("chicken-breast", 160, 100, 250, True, "protein"),
            ("basmati-rice", 80, 50, 130, True, "carbohydrate"),
            ("broccoli", 75, 30, 150, False, "fibre"),
            ("carrot", 75, 30, 150, False, "micronutrient_source"),
        ),
    ),
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_nutrition_catalogue_meal_slot_values",
        "nutrition_catalogue_meals",
        type_="check",
    )
    op.alter_column("nutrition_catalogue_meals", "slot_role", new_column_name="category")
    op.execute(
        "UPDATE nutrition_catalogue_meals SET category = "
        "CASE WHEN category = 'snack' THEN 'snack' ELSE 'lunch' END"
    )
    op.create_check_constraint(
        "ck_nutrition_catalogue_meal_category_values",
        "nutrition_catalogue_meals",
        f"category IN ({', '.join(repr(value) for value in CATEGORIES)})",
    )

    op.alter_column("nutrition_catalogue_meal_items", "grams", new_column_name="reference_grams")
    op.add_column("nutrition_catalogue_meal_items", sa.Column("min_grams", sa.Numeric(20, 8)))
    op.add_column("nutrition_catalogue_meal_items", sa.Column("max_grams", sa.Numeric(20, 8)))
    op.add_column(
        "nutrition_catalogue_meal_items",
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("nutrition_catalogue_meal_items", sa.Column("functional_role", sa.String(32)))
    op.execute(
        "UPDATE nutrition_catalogue_meal_items "
        "SET min_grams = reference_grams, max_grams = reference_grams"
    )
    op.alter_column("nutrition_catalogue_meal_items", "min_grams", nullable=False)
    op.alter_column("nutrition_catalogue_meal_items", "max_grams", nullable=False)
    op.drop_constraint(
        "ck_nutrition_catalogue_meal_item_grams_positive",
        "nutrition_catalogue_meal_items",
        type_="check",
    )
    op.create_check_constraint(
        "ck_nutrition_catalogue_meal_item_bounds",
        "nutrition_catalogue_meal_items",
        "min_grams > 0 AND min_grams <= reference_grams AND reference_grams <= max_grams",
    )
    op.create_check_constraint(
        "ck_nutrition_catalogue_meal_item_functional_role_values",
        "nutrition_catalogue_meal_items",
        f"functional_role IN ({', '.join(repr(value) for value in ROLES)})",
    )
    op.create_unique_constraint(
        "uq_nutrition_catalogue_meal_item_food",
        "nutrition_catalogue_meal_items",
        ["meal_id", "food_id"],
    )
    _seed(op.get_bind())


def downgrade() -> None:
    meal_ids = [
        uuid5(NAMESPACE_URL, f"fitsho:nutrition:meal:{category}:initial") for category in CATEGORIES
    ]
    meals = sa.table("nutrition_catalogue_meals", sa.column("id", sa.Uuid()))
    op.get_bind().execute(meals.delete().where(meals.c.id.in_(meal_ids)))
    op.drop_constraint(
        "uq_nutrition_catalogue_meal_item_food",
        "nutrition_catalogue_meal_items",
        type_="unique",
    )
    op.drop_constraint(
        "ck_nutrition_catalogue_meal_item_functional_role_values",
        "nutrition_catalogue_meal_items",
        type_="check",
    )
    op.drop_constraint(
        "ck_nutrition_catalogue_meal_item_bounds",
        "nutrition_catalogue_meal_items",
        type_="check",
    )
    op.create_check_constraint(
        "ck_nutrition_catalogue_meal_item_grams_positive",
        "nutrition_catalogue_meal_items",
        "reference_grams > 0",
    )
    op.drop_column("nutrition_catalogue_meal_items", "functional_role")
    op.drop_column("nutrition_catalogue_meal_items", "is_required")
    op.drop_column("nutrition_catalogue_meal_items", "max_grams")
    op.drop_column("nutrition_catalogue_meal_items", "min_grams")
    op.alter_column("nutrition_catalogue_meal_items", "reference_grams", new_column_name="grams")
    op.drop_constraint(
        "ck_nutrition_catalogue_meal_category_values",
        "nutrition_catalogue_meals",
        type_="check",
    )
    op.execute(
        "UPDATE nutrition_catalogue_meals SET category = "
        "CASE WHEN category = 'snack' THEN 'snack' ELSE 'main_meal' END"
    )
    op.alter_column("nutrition_catalogue_meals", "category", new_column_name="slot_role")
    op.create_check_constraint(
        "ck_nutrition_catalogue_meal_slot_values",
        "nutrition_catalogue_meals",
        "slot_role IN ('main_meal', 'snack')",
    )


def _seed(connection: sa.Connection) -> None:
    foods = sa.table(
        "nutrition_catalogue_foods",
        sa.column("id", sa.Uuid()),
        sa.column("slug", sa.String()),
        sa.column("verification_status", sa.String()),
    )
    meals = sa.table(
        "nutrition_catalogue_meals",
        sa.column("id", sa.Uuid()),
        sa.column("name_fa", sa.String()),
        sa.column("name_en", sa.String()),
        sa.column("category", sa.String()),
        sa.column("verification_status", sa.String()),
    )
    items_table = sa.table(
        "nutrition_catalogue_meal_items",
        sa.column("id", sa.Uuid()),
        sa.column("meal_id", sa.Uuid()),
        sa.column("food_id", sa.Uuid()),
        sa.column("reference_grams", sa.Numeric()),
        sa.column("min_grams", sa.Numeric()),
        sa.column("max_grams", sa.Numeric()),
        sa.column("is_required", sa.Boolean()),
        sa.column("functional_role", sa.String()),
    )
    for category, name_fa, name_en, item_seeds in SEEDS:
        meal_id = uuid5(NAMESPACE_URL, f"fitsho:nutrition:meal:{category}:initial")
        food_rows = {
            row.slug: row
            for row in connection.execute(
                sa.select(foods.c.id, foods.c.slug, foods.c.verification_status).where(
                    foods.c.slug.in_(slug for slug, *_ in item_seeds)
                )
            )
        }
        if len(food_rows) != len(item_seeds):
            raise RuntimeError(f"Cannot seed {category} meal: food catalogue is incomplete")
        connection.execute(
            meals.insert().values(
                id=meal_id,
                name_fa=name_fa,
                name_en=name_en,
                category=category,
                verification_status=(
                    "verified"
                    if all(row.verification_status == "verified" for row in food_rows.values())
                    else "draft"
                ),
            )
        )
        connection.execute(
            items_table.insert(),
            [
                {
                    "id": uuid5(NAMESPACE_URL, f"fitsho:nutrition:meal:{category}:{slug}"),
                    "meal_id": meal_id,
                    "food_id": food_rows[slug].id,
                    "reference_grams": reference,
                    "min_grams": minimum,
                    "max_grams": maximum,
                    "is_required": required,
                    "functional_role": role,
                }
                for slug, reference, minimum, maximum, required, role in item_seeds
            ],
        )
