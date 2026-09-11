"""add nutrition notification preference"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260911_136"
down_revision: str | Sequence[str] | None = "20260911_135"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "notification_preferences",
        sa.Column("nutrition_updates", sa.Boolean(), server_default=sa.true(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("notification_preferences", "nutrition_updates")
