"""add stable meal catalogue codes"""

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa

from alembic import op

revision: str = "20260812_66"
down_revision: str | Sequence[str] | None = "20260812_65"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STARTER_CODES = {
    "breakfast": "BF02",
    "lunch": "LU01",
    "post_workout": "PW01",
    "snack": "SN01",
    "dinner": "DN01",
}


def upgrade() -> None:
    op.add_column("nutrition_catalogue_meals", sa.Column("code", sa.String(length=20)))
    meals = sa.table(
        "nutrition_catalogue_meals", sa.column("id", sa.Uuid()), sa.column("code", sa.String())
    )
    connection = op.get_bind()
    for category, code in STARTER_CODES.items():
        meal_id = uuid5(NAMESPACE_URL, f"fitsho:nutrition:meal:{category}:initial")
        connection.execute(meals.update().where(meals.c.id == meal_id).values(code=code))
    op.execute(
        "UPDATE nutrition_catalogue_meals "
        "SET code = 'LEGACY-' || upper(substr(replace(id::text, '-', ''), 1, 12)) "
        "WHERE code IS NULL"
    )
    op.alter_column("nutrition_catalogue_meals", "code", nullable=False)
    op.create_unique_constraint(
        "uq_nutrition_catalogue_meals_code", "nutrition_catalogue_meals", ["code"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_nutrition_catalogue_meals_code", "nutrition_catalogue_meals", type_="unique"
    )
    op.drop_column("nutrition_catalogue_meals", "code")
