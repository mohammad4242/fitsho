"""create provider-neutral AI task settings and encrypted credentials"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_22"
down_revision: str | Sequence[str] | None = "20260803_21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_provider_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "provider",
            sa.Enum(
                "openrouter",
                name="ck_ai_provider_credentials_provider_values",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("encrypted_api_key", sa.String(length=2048), nullable=False),
        sa.Column("key_last_four", sa.String(length=4), nullable=False),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider"),
    )
    op.create_index(
        "ix_ai_provider_credentials_updated_by_user_id",
        "ai_provider_credentials",
        ["updated_by_user_id"],
    )
    op.create_table(
        "ai_task_configs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "task_type",
            sa.Enum(
                "workout_plan_generation",
                "body_photo_analysis",
                "progress_comparison",
                "specialist_summary",
                name="ck_ai_task_configs_task_type_values",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "provider",
            sa.Enum(
                "openrouter",
                name="ck_ai_task_configs_provider_values",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("primary_model_id", sa.String(length=300), nullable=True),
        sa.Column(
            "fallback_model_ids", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False
        ),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("temperature", sa.Float(), server_default="0", nullable=False),
        sa.Column("max_output_tokens", sa.Integer(), server_default="4096", nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), server_default="45", nullable=False),
        sa.Column("minimum_confidence", sa.Float(), server_default="0.7", nullable=False),
        sa.Column("max_cost_per_request", sa.Numeric(12, 6), nullable=True),
        sa.Column(
            "routing_restrictions", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False
        ),
        sa.Column("last_successful_connection_test_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_model_catalog_refresh_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("last_error_message", sa.String(length=500), nullable=True),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("temperature >= 0 AND temperature <= 2", name="ck_ai_task_temp_range"),
        sa.CheckConstraint("max_output_tokens > 0", name="ck_ai_task_tokens_positive"),
        sa.CheckConstraint("timeout_seconds > 0", name="ck_ai_task_timeout_positive"),
        sa.CheckConstraint(
            "minimum_confidence >= 0 AND minimum_confidence <= 1",
            name="ck_ai_task_confidence_range",
        ),
        sa.CheckConstraint(
            "max_cost_per_request IS NULL OR max_cost_per_request >= 0",
            name="ck_ai_task_cost_nonnegative",
        ),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_type"),
    )
    op.create_table(
        "ai_model_catalog_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "provider",
            sa.Enum(
                "openrouter",
                name="ck_ai_model_catalog_provider_values",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("model_id", sa.String(length=300), nullable=False),
        sa.Column("display_name", sa.String(length=300), nullable=False),
        sa.Column("provider_family", sa.String(length=120), nullable=False),
        sa.Column("supports_text_input", sa.Boolean(), nullable=False),
        sa.Column("supports_image_input", sa.Boolean(), nullable=False),
        sa.Column("supports_structured_output", sa.Boolean(), nullable=False),
        sa.Column("context_length", sa.Integer(), nullable=True),
        sa.Column("input_price_per_token", sa.Numeric(24, 16), nullable=True),
        sa.Column("output_price_per_token", sa.Numeric(24, 16), nullable=True),
        sa.Column("available", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("refreshed_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "model_id", name="uq_ai_model_catalog_provider_model"),
    )
    op.create_table(
        "ai_audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "action",
            sa.Enum(
                "config_updated",
                "credential_replaced",
                "connection_tested",
                "model_catalog_refreshed",
                name="ck_ai_audit_events_action_values",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("task_type", sa.String(length=64), nullable=True),
        sa.Column("provider", sa.String(length=32), nullable=True),
        sa.Column(
            "changed_fields", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_audit_events_actor_user_id", "ai_audit_events", ["actor_user_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_audit_events_actor_user_id", table_name="ai_audit_events")
    op.drop_table("ai_audit_events")
    op.drop_table("ai_model_catalog_entries")
    op.drop_table("ai_task_configs")
    op.drop_index(
        "ix_ai_provider_credentials_updated_by_user_id",
        table_name="ai_provider_credentials",
    )
    op.drop_table("ai_provider_credentials")
