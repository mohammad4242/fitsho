"""add meal catalogue images"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260812_67m"
down_revision: str | Sequence[str] | None = "20260812_66"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "nutrition_catalogue_meals",
        sa.Column("image_path", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("nutrition_catalogue_meals", "image_path")
