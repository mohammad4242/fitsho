"""persist preferred weekdays and priority muscles in user profiles"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260818_98"
down_revision: str | Sequence[str] | None = "20260818_97"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("preferred_weekdays", sa.JSON(), nullable=True))
    op.add_column("user_profiles", sa.Column("priority_muscles", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("user_profiles", "priority_muscles")
    op.drop_column("user_profiles", "preferred_weekdays")
