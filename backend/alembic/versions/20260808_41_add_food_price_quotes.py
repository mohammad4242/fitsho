# ruff: noqa: E501
"""add food price update engine storage"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_41"
down_revision: str | Sequence[str] | None = "20260808_40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "nutrition_price_providers",
        sa.Column("code", sa.String(64), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("priority", sa.SmallInteger(), nullable=False, server_default="100"),
        sa.Column("fresh_hours", sa.SmallInteger(), nullable=False, server_default="24"),
        sa.Column("stale_hours", sa.SmallInteger(), nullable=False, server_default="168"),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(500)),
    )
    op.create_table(
        "nutrition_food_price_mappings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("food_id", sa.Uuid(), nullable=False),
        sa.Column("provider_code", sa.String(64), nullable=False),
        sa.Column("provider_product_id", sa.String(160), nullable=False),
        sa.Column("region", sa.String(120)),
        sa.Column("match_alias", sa.String(160)),
        sa.Column("match_confidence", sa.Numeric(5, 4), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(["food_id"], ["nutrition_catalogue_foods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["provider_code"], ["nutrition_price_providers.code"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "provider_code", "provider_product_id", name="uq_price_mapping_provider_product"
        ),
    )
    op.create_table(
        "nutrition_food_price_quotes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("food_id", sa.Uuid(), nullable=False),
        sa.Column("provider_code", sa.String(64), nullable=False),
        sa.Column("provider_product_id", sa.String(160), nullable=False),
        sa.Column("package_quantity", sa.Numeric(20, 8), nullable=False),
        sa.Column("package_unit", sa.String(12), nullable=False),
        sa.Column("normal_price_irr", sa.Numeric(20, 2)),
        sa.Column("promotional_price_irr", sa.Numeric(20, 2)),
        sa.Column("normalized_normal_irr", sa.Numeric(20, 8)),
        sa.Column("normalized_promotional_irr", sa.Numeric(20, 8)),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("raw_quote", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["food_id"], ["nutrition_catalogue_foods.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["provider_code"], ["nutrition_price_providers.code"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            "package_quantity > 0", name="ck_nutrition_price_quote_quantity_positive"
        ),
    )
    op.create_index(
        "ix_nutrition_price_quotes_food_observed",
        "nutrition_food_price_quotes",
        ["food_id", "observed_at"],
    )
    op.create_table(
        "nutrition_food_price_references",
        sa.Column("food_id", sa.Uuid(), primary_key=True),
        sa.Column("canonical_unit", sa.String(24), nullable=False),
        sa.Column("reference_price_toman", sa.Numeric(20, 8), nullable=False),
        sa.Column("sample_count", sa.SmallInteger(), nullable=False),
        sa.Column("confidence", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["food_id"], ["nutrition_catalogue_foods.id"], ondelete="RESTRICT"),
    )
    op.create_table(
        "nutrition_food_price_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("food_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_unit", sa.String(24), nullable=False),
        sa.Column("reference_price_toman", sa.Numeric(20, 8), nullable=False),
        sa.Column("sample_count", sa.SmallInteger(), nullable=False),
        sa.Column("confidence", sa.String(16), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_quote_ids", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["food_id"], ["nutrition_catalogue_foods.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_nutrition_price_history_food_id", "nutrition_food_price_history", ["food_id"]
    )
    op.create_table(
        "nutrition_food_price_update_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("foods_attempted", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("foods_updated", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("foods_unchanged", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("foods_needing_review", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("provider_failures", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
        sa.UniqueConstraint("scheduled_for", name="uq_nutrition_price_run_scheduled_for"),
    )
    op.create_table(
        "nutrition_food_price_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("food_id", sa.Uuid(), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("candidate_reference_price_toman", sa.Numeric(20, 8)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["nutrition_food_price_update_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["food_id"], ["nutrition_catalogue_foods.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_nutrition_price_reviews_run_id", "nutrition_food_price_reviews", ["run_id"])
    op.create_index(
        "ix_nutrition_price_reviews_food_id", "nutrition_food_price_reviews", ["food_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_nutrition_price_reviews_food_id", table_name="nutrition_food_price_reviews")
    op.drop_index("ix_nutrition_price_reviews_run_id", table_name="nutrition_food_price_reviews")
    op.drop_table("nutrition_food_price_reviews")
    op.drop_table("nutrition_food_price_update_runs")
    op.drop_index("ix_nutrition_price_history_food_id", table_name="nutrition_food_price_history")
    op.drop_table("nutrition_food_price_history")
    op.drop_table("nutrition_food_price_references")
    op.drop_index(
        "ix_nutrition_price_quotes_food_observed", table_name="nutrition_food_price_quotes"
    )
    op.drop_table("nutrition_food_price_quotes")
    op.drop_table("nutrition_food_price_mappings")
    op.drop_table("nutrition_price_providers")
