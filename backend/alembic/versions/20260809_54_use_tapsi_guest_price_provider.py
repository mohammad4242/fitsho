"""use Tapsi anonymous guest catalogue provider"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_54"
down_revision: str | Sequence[str] | None = "20260809_53"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE nutrition_price_providers "
            "SET parser_version = 'tapsi-guest-v1' WHERE code = 'tapsi_shop'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE nutrition_price_providers "
            "SET parser_version = 'tapsi-rendered-v1' WHERE code = 'tapsi_shop'"
        )
    )
