"""add free meal tracking source"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260812_69"
down_revision: str | Sequence[str] | None = "20260812_68"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_nutrition_consumption_source_values",
        "nutrition_consumption_entries",
        type_="check",
    )
    op.create_check_constraint(
        "ck_nutrition_consumption_source_values",
        "nutrition_consumption_entries",
        "source IN ('planned_confirmed', 'planned_adjusted', 'catalogue_manual', "
        "'photo_estimated_confirmed', 'photo_estimated_edited', 'quick_approximation', "
        "'professional_entry', 'free_meal')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM nutrition_consumption_entries WHERE source = 'free_meal'")
    op.drop_constraint(
        "ck_nutrition_consumption_source_values",
        "nutrition_consumption_entries",
        type_="check",
    )
    op.create_check_constraint(
        "ck_nutrition_consumption_source_values",
        "nutrition_consumption_entries",
        "source IN ('planned_confirmed', 'planned_adjusted', 'catalogue_manual', "
        "'photo_estimated_confirmed', 'photo_estimated_edited', 'quick_approximation', "
        "'professional_entry')",
    )
