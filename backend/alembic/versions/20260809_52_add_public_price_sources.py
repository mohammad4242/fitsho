"""add durable public food price source registry"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_52"
down_revision: str | Sequence[str] | None = "20260809_51"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PUBLIC_PROVIDERS = (
    ("digikala", "Digikala", "https://www.digikala.com/"),
    ("torob", "Torob", "https://torob.com/"),
    ("basalam_public", "Basalam", "https://basalam.com/"),
    ("okala", "Okala", "https://www.okala.com/"),
    ("snapp_market", "Snapp Market", "https://snapp.market/"),
    ("hyperstar", "Hyperstar", "https://www.hyperstariran.com/"),
    ("shahrvand", "Shahrvand", "https://shahrvand.ir/"),
    ("refah", "Refah", "https://refah.ir/"),
    ("emalls", "Emalls", "https://emalls.ir/"),
    ("tehran_market_official", "Tehran Market Official", "https://market.tehran.ir/"),
)


def upgrade() -> None:
    op.add_column(
        "nutrition_price_providers",
        sa.Column("minimum_sources", sa.SmallInteger(), nullable=False, server_default="3"),
    )
    op.add_column("nutrition_price_providers", sa.Column("base_url", sa.String(500)))
    op.add_column("nutrition_price_providers", sa.Column("parser_version", sa.String(64)))

    op.add_column("nutrition_food_price_mappings", sa.Column("public_product_url", sa.String(500)))
    op.add_column(
        "nutrition_food_price_mappings", sa.Column("discovered_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "nutrition_food_price_mappings", sa.Column("last_verified_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "nutrition_food_price_mappings", sa.Column("broken_at", sa.DateTime(timezone=True))
    )

    op.add_column(
        "nutrition_food_price_quotes", sa.Column("provider_observation_key", sa.String(200))
    )
    op.add_column(
        "nutrition_food_price_quotes", sa.Column("fetched_at", sa.DateTime(timezone=True))
    )
    op.add_column("nutrition_food_price_quotes", sa.Column("parser_version", sa.String(64)))
    op.create_unique_constraint(
        "uq_nutrition_price_quote_provider_observation",
        "nutrition_food_price_quotes",
        ["provider_code", "provider_observation_key"],
    )

    op.add_column(
        "nutrition_food_price_history",
        sa.Column("accepted_quote_ids", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "nutrition_food_price_history",
        sa.Column("rejected_quote_ids", sa.JSON(), nullable=False, server_default="[]"),
    )

    op.add_column(
        "nutrition_food_price_update_runs",
        sa.Column("trigger_kind", sa.String(16), nullable=False, server_default="manual"),
    )
    op.add_column(
        "nutrition_food_price_update_runs",
        sa.Column(
            "policy_version", sa.String(64), nullable=False, server_default="public-price-v2"
        ),
    )
    op.add_column(
        "nutrition_food_price_update_runs",
        sa.Column("failure_codes", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.create_check_constraint(
        "ck_nutrition_price_run_trigger_values",
        "nutrition_food_price_update_runs",
        "trigger_kind IN ('manual', 'scheduled', 'catch_up')",
    )

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
                "code": code,
                "kind": "public_catalog",
                "name": name,
                "enabled": False,
                "priority": index * 10,
                "fresh_hours": 48,
                "stale_hours": 168,
                "minimum_sources": 3,
                "base_url": base_url,
                "parser_version": "public-page-v1",
            }
            for index, (code, name, base_url) in enumerate(PUBLIC_PROVIDERS, start=1)
        ],
    )


def downgrade() -> None:
    codes = ", ".join(f"'{code}'" for code, _, _ in PUBLIC_PROVIDERS)
    op.execute(sa.text(f"DELETE FROM nutrition_price_providers WHERE code IN ({codes})"))
    op.drop_constraint(
        "ck_nutrition_price_run_trigger_values",
        "nutrition_food_price_update_runs",
        type_="check",
    )
    op.drop_column("nutrition_food_price_update_runs", "failure_codes")
    op.drop_column("nutrition_food_price_update_runs", "policy_version")
    op.drop_column("nutrition_food_price_update_runs", "trigger_kind")
    op.drop_column("nutrition_food_price_history", "rejected_quote_ids")
    op.drop_column("nutrition_food_price_history", "accepted_quote_ids")
    op.drop_constraint(
        "uq_nutrition_price_quote_provider_observation",
        "nutrition_food_price_quotes",
        type_="unique",
    )
    op.drop_column("nutrition_food_price_quotes", "parser_version")
    op.drop_column("nutrition_food_price_quotes", "fetched_at")
    op.drop_column("nutrition_food_price_quotes", "provider_observation_key")
    op.drop_column("nutrition_food_price_mappings", "broken_at")
    op.drop_column("nutrition_food_price_mappings", "last_verified_at")
    op.drop_column("nutrition_food_price_mappings", "discovered_at")
    op.drop_column("nutrition_food_price_mappings", "public_product_url")
    op.drop_column("nutrition_price_providers", "parser_version")
    op.drop_column("nutrition_price_providers", "base_url")
    op.drop_column("nutrition_price_providers", "minimum_sources")
