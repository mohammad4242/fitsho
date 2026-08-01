"""create AI model routing

Revision ID: 20260730_09
Revises: 20260730_08
Create Date: 2026-07-30 23:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.ai.catalog import DOCUMENTED_ZEN_MODELS, documented_model_uuid

revision: str = "20260730_09"
down_revision: str | Sequence[str] | None = "20260730_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_models",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("model_id", sa.String(length=160), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("api_kind", sa.String(length=32)),
        sa.Column("billing_class", sa.String(length=16)),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="1000", nullable=False),
        sa.Column("is_custom", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "classification_required",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("last_checked_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.String(length=80)),
        sa.Column("last_error_message", sa.String(length=500)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("priority >= 0", name="ck_ai_models_priority_nonnegative"),
        sa.CheckConstraint(
            "NOT classification_required OR "
            "(api_kind IS NULL AND billing_class IS NULL AND NOT is_enabled)",
            name="ck_ai_models_unclassified_disabled",
        ),
        sa.CheckConstraint(
            "NOT is_enabled OR "
            "(api_kind IS NOT NULL AND billing_class IS NOT NULL AND NOT classification_required)",
            name="ck_ai_models_enabled_classified",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_id"),
    )
    op.create_index(
        "ix_ai_models_automatic_route",
        "ai_models",
        ["is_enabled", "billing_class", "priority"],
    )
    op.create_table(
        "ai_routing_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(length=16), server_default="manual", nullable=False),
        sa.Column("manual_model_id", sa.Uuid()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name="ck_ai_routing_settings_singleton"),
        sa.ForeignKeyConstraint(["manual_model_id"], ["ai_models.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    ai_models = sa.table(
        "ai_models",
        sa.column("id", sa.Uuid()),
        sa.column("model_id", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("api_kind", sa.String()),
        sa.column("billing_class", sa.String()),
        sa.column("is_enabled", sa.Boolean()),
        sa.column("priority", sa.Integer()),
        sa.column("is_custom", sa.Boolean()),
        sa.column("classification_required", sa.Boolean()),
    )
    op.bulk_insert(
        ai_models,
        [
            {
                "id": documented_model_uuid(entry.model_id),
                "model_id": entry.model_id,
                "display_name": entry.display_name,
                "api_kind": entry.api_kind.value,
                "billing_class": entry.billing_class.value,
                "is_enabled": True,
                "priority": 10 if entry.model_id == "nemotron-3-ultra-free" else 1000,
                "is_custom": False,
                "classification_required": False,
            }
            for entry in DOCUMENTED_ZEN_MODELS.values()
        ],
    )
    settings = sa.table(
        "ai_routing_settings",
        sa.column("id", sa.Integer()),
        sa.column("mode", sa.String()),
        sa.column("manual_model_id", sa.Uuid()),
    )
    op.bulk_insert(
        settings,
        [
            {
                "id": 1,
                "mode": "manual",
                "manual_model_id": documented_model_uuid("nemotron-3-ultra-free"),
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("ai_routing_settings")
    op.drop_index("ix_ai_models_automatic_route", table_name="ai_models")
    op.drop_table("ai_models")
