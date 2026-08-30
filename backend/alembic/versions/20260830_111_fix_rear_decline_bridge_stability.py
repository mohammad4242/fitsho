"""Set the canonical stability demand for Rear Decline Bridge."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260830_111"
down_revision: str | Sequence[str] | None = "20260830_110"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WHERE = "source = 'free-exercise-db' AND source_id = '0668'"


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE exercises SET stability_demand = 'low' "
            f"WHERE {_WHERE}"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE exercises SET stability_demand = NULL "
            f"WHERE {_WHERE} AND stability_demand = 'low'"
        )
    )
