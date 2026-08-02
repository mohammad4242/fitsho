"""add template programming rationale"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "20260802_17"
down_revision = "9a9b380d40b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "training_program_templates",
        sa.Column(
            "programming_rationale",
            sa.JSON(),
            server_default=sa.text("'[]'::json"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("training_program_templates", "programming_rationale")
