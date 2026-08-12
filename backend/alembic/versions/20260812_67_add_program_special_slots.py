"""add nutrition program codes and special slots"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260812_67"
down_revision: str | Sequence[str] | None = "20260812_66"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("nutrition_programs", sa.Column("code", sa.String(length=20)))
    op.execute("UPDATE nutrition_programs SET code = upper(substr(replace(slug, '-', ''), 1, 20))")
    op.alter_column("nutrition_programs", "code", nullable=False)
    op.create_unique_constraint("uq_nutrition_programs_code", "nutrition_programs", ["code"])
    op.add_column(
        "nutrition_program_slots",
        sa.Column("kind", sa.String(length=20), server_default="catalogue_meal", nullable=False),
    )
    op.alter_column("nutrition_program_slots", "meal_id", nullable=True)
    op.create_check_constraint(
        "ck_nutrition_program_slots_kind_values",
        "nutrition_program_slots",
        "kind IN ('catalogue_meal', 'free_meal')",
    )
    op.create_check_constraint(
        "ck_nutrition_program_slots_relationship",
        "nutrition_program_slots",
        "(kind = 'catalogue_meal' AND meal_id IS NOT NULL) OR "
        "(kind = 'free_meal' AND meal_id IS NULL AND category = 'lunch')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_nutrition_program_slots_relationship", "nutrition_program_slots", type_="check"
    )
    op.drop_constraint(
        "ck_nutrition_program_slots_kind_values", "nutrition_program_slots", type_="check"
    )
    op.execute("DELETE FROM nutrition_program_slots WHERE kind = 'free_meal'")
    op.alter_column("nutrition_program_slots", "meal_id", nullable=False)
    op.drop_column("nutrition_program_slots", "kind")
    op.drop_constraint("uq_nutrition_programs_code", "nutrition_programs", type_="unique")
    op.drop_column("nutrition_programs", "code")
