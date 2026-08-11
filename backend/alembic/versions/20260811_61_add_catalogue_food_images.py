"""add catalogue food images"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260811_61"
down_revision: str | Sequence[str] | None = "20260811_60"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "nutrition_catalogue_foods",
        sa.Column("image_path", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("nutrition_catalogue_foods", "image_path")
