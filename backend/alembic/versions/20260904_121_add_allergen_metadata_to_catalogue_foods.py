"""add allergen metadata to catalogue foods"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260904_121"
down_revision: str | Sequence[str] | None = "20260904_120"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "nutrition_catalogue_foods",
        sa.Column("allergen_tags", sa.JSON(), server_default="[]", nullable=False),
    )
    op.add_column(
        "nutrition_catalogue_foods",
        sa.Column(
            "allergen_metadata_verified",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("nutrition_catalogue_foods", "allergen_metadata_verified")
    op.drop_column("nutrition_catalogue_foods", "allergen_tags")
