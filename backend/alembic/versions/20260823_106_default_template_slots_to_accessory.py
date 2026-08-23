"""default new training template slots to accessory"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260823_106"
down_revision: str | Sequence[str] | None = "20260823_105"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "training_program_template_slots",
        "adaptation_priority",
        server_default=sa.text("'accessory'"),
    )


def downgrade() -> None:
    op.alter_column(
        "training_program_template_slots",
        "adaptation_priority",
        server_default=sa.text("'core'"),
    )
