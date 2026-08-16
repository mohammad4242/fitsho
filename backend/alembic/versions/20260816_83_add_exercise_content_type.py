"""classify exercise catalogue content"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260816_83"
down_revision: str | Sequence[str] | None = "20260816_82"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VALUE_CONSTRAINT = "ck_exercises_content_type_values"
_INDEX = "ix_exercises_content_type"


def upgrade() -> None:
    op.add_column(
        "exercises",
        sa.Column(
            "content_type",
            sa.String(length=16),
            nullable=False,
            server_default="exercise",
        ),
    )
    op.execute(sa.text("UPDATE exercises SET content_type = 'exercise'"))
    op.create_check_constraint(
        _VALUE_CONSTRAINT,
        "exercises",
        "content_type IN ('exercise', 'guide')",
    )
    op.create_index(_INDEX, "exercises", ["content_type"])


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="exercises")
    op.drop_constraint(_VALUE_CONSTRAINT, "exercises", type_="check")
    op.drop_column("exercises", "content_type")
