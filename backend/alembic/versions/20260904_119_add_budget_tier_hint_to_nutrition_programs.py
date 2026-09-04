"""add budget tier hint to nutrition programs"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260904_119"
down_revision: str | Sequence[str] | None = "20260903_118"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BUDGET_TIERS = ("economy", "normal", "varied")


def upgrade() -> None:
    op.add_column(
        "nutrition_programs",
        sa.Column("budget_tier_hint", sa.String(length=20), nullable=True),
    )
    tier_values = ", ".join(repr(v) for v in BUDGET_TIERS)
    op.create_check_constraint(
        "ck_nutrition_programs_budget_tier_hint_values",
        "nutrition_programs",
        f"budget_tier_hint IS NULL OR budget_tier_hint IN ({tier_values})",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_nutrition_programs_budget_tier_hint_values",
        "nutrition_programs",
        type_="check",
    )
    op.drop_column("nutrition_programs", "budget_tier_hint")
