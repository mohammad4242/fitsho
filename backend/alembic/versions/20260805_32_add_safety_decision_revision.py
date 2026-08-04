"""add deterministic safety decision revision"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260805_32"
down_revision: str | Sequence[str] | None = "20260805_31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "nutrition_safety_decisions",
        sa.Column("revision", sa.SmallInteger(), nullable=True),
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   row_number() OVER (
                       PARTITION BY user_id ORDER BY created_at, id
                   ) AS revision
            FROM nutrition_safety_decisions
        )
        UPDATE nutrition_safety_decisions AS decisions
        SET revision = ranked.revision
        FROM ranked
        WHERE decisions.id = ranked.id
        """
    )
    op.alter_column("nutrition_safety_decisions", "revision", nullable=False)
    op.create_check_constraint(
        "ck_nutrition_safety_decisions_revision_positive",
        "nutrition_safety_decisions",
        "revision > 0",
    )
    op.create_unique_constraint(
        "uq_nutrition_safety_decisions_user_revision",
        "nutrition_safety_decisions",
        ["user_id", "revision"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_nutrition_safety_decisions_user_revision",
        "nutrition_safety_decisions",
    )
    op.drop_constraint(
        "ck_nutrition_safety_decisions_revision_positive",
        "nutrition_safety_decisions",
    )
    op.drop_column("nutrition_safety_decisions", "revision")
