"""Retain the price quote IDs that caused a review."""

import sqlalchemy as sa

from alembic import op

revision: str = "20260901_116"
down_revision: str | None = "20260901_115"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "nutrition_food_price_reviews",
        sa.Column(
            "source_quote_ids",
            sa.JSON(),
            nullable=True,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.execute(
        sa.text(
            "UPDATE nutrition_food_price_reviews "
            "SET source_quote_ids = '[]'::json WHERE source_quote_ids IS NULL"
        )
    )
    op.alter_column(
        "nutrition_food_price_reviews",
        "source_quote_ids",
        existing_type=sa.JSON(),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("nutrition_food_price_reviews", "source_quote_ids")
