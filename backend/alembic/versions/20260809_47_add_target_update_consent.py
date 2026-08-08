"""add explicit nutrition target update consent audit"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_47"
down_revision: str | Sequence[str] | None = "20260809_46"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "nutrition_target_update_consents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("previous_goal", sa.String(48), nullable=False),
        sa.Column("requested_goal", sa.String(48), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "estimate_id", sa.Uuid(), sa.ForeignKey("nutrition_estimates.id", ondelete="SET NULL")
        ),
    )
    op.create_index(
        "ix_nutrition_target_update_consents_user_id",
        "nutrition_target_update_consents",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_table("nutrition_target_update_consents")
