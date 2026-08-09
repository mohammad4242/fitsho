"""resolve nutrition food preferences to canonical catalogue foods"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_56"
down_revision: str | Sequence[str] | None = "20260809_55"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "nutrition_food_items",
        sa.Column("catalogue_food_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_nutrition_food_items_catalogue_food_id",
        "nutrition_food_items",
        "nutrition_catalogue_foods",
        ["catalogue_food_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_nutrition_food_items_catalogue_food_id",
        "nutrition_food_items",
        ["catalogue_food_id"],
    )
    op.execute(
        """
        UPDATE nutrition_food_items AS item
        SET catalogue_food_id = match.food_id
        FROM (
            SELECT alias.normalized_alias, min(alias.food_id::text)::uuid AS food_id
            FROM nutrition_catalogue_food_aliases AS alias
            GROUP BY alias.normalized_alias
            HAVING count(DISTINCT alias.food_id) = 1
        ) AS match
        WHERE item.kind IN ('favourite', 'disliked')
          AND item.normalized_name = match.normalized_alias
        """
    )


def downgrade() -> None:
    op.drop_index(
        "ix_nutrition_food_items_catalogue_food_id",
        table_name="nutrition_food_items",
    )
    op.drop_constraint(
        "fk_nutrition_food_items_catalogue_food_id",
        "nutrition_food_items",
        type_="foreignkey",
    )
    op.drop_column("nutrition_food_items", "catalogue_food_id")
