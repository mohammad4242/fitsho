"""add approved Tapsi Shop price provider"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_53"
down_revision: str | Sequence[str] | None = "20260809_52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    provider_table = sa.table(
        "nutrition_price_providers",
        sa.column("code", sa.String),
        sa.column("kind", sa.String),
        sa.column("name", sa.String),
        sa.column("enabled", sa.Boolean),
        sa.column("priority", sa.SmallInteger),
        sa.column("fresh_hours", sa.SmallInteger),
        sa.column("stale_hours", sa.SmallInteger),
        sa.column("minimum_sources", sa.SmallInteger),
        sa.column("base_url", sa.String),
        sa.column("parser_version", sa.String),
    )
    op.bulk_insert(
        provider_table,
        [
            {
                "code": "tapsi_shop",
                "kind": "public_catalog",
                "name": "Tapsi Shop",
                "enabled": False,
                "priority": 30,
                "fresh_hours": 48,
                "stale_hours": 168,
                "minimum_sources": 3,
                "base_url": "https://tapsi.shop/",
                "parser_version": "tapsi-rendered-v1",
            }
        ],
    )
    op.execute(
        sa.text(
            "UPDATE nutrition_price_providers "
            "SET parser_version = 'basalam-public-v1' WHERE code = 'basalam_public'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE nutrition_price_providers "
            "SET parser_version = 'digikala-public-v1' WHERE code = 'digikala'"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM nutrition_price_providers WHERE code = 'tapsi_shop'"))
    op.execute(
        sa.text(
            "UPDATE nutrition_price_providers SET parser_version = 'public-page-v1' "
            "WHERE code IN ('basalam_public', 'digikala')"
        )
    )
