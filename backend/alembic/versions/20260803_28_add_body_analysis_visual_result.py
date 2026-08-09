"""store schema v2 visual body-analysis results"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_28"
down_revision: str | Sequence[str] | None = "20260803_27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("body_analyses", sa.Column("visual_result", sa.JSON(), nullable=True))
    op.add_column(
        "body_analysis_result_versions", sa.Column("visual_result", sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("body_analysis_result_versions", "visual_result")
    op.drop_column("body_analyses", "visual_result")
