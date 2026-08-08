"""add OpenRouter food photo estimation records"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_46"
down_revision: str | Sequence[str] | None = "20260809_45"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_ai_task_configs_task_type_values", "ai_task_configs", type_="check")
    op.create_check_constraint(
        "ck_ai_task_configs_task_type_values",
        "ai_task_configs",
        "task_type IN ('workout_plan_generation','body_photo_analysis','progress_comparison',"
        "'specialist_summary','food_photo_estimation')",
    )
    op.create_table(
        "nutrition_food_photo_estimates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("storage_key", sa.String(500), nullable=False, unique=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model_id", sa.String(300)),
        sa.Column("provider_request_id", sa.String(160)),
        sa.Column("raw_estimate", sa.JSON(), nullable=False),
        sa.Column("mapped_items", sa.JSON(), nullable=False),
        sa.Column("input_tokens", sa.BigInteger()),
        sa.Column("output_tokens", sa.BigInteger()),
        sa.Column("estimated_cost", sa.Numeric(12, 6)),
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('estimated','confirmed','deleted','failed')",
            name="ck_nutrition_food_photo_status",
        ),
    )
    op.create_index(
        "ix_nutrition_food_photo_estimates_user_id", "nutrition_food_photo_estimates", ["user_id"]
    )


def downgrade() -> None:
    op.drop_table("nutrition_food_photo_estimates")
    op.drop_constraint("ck_ai_task_configs_task_type_values", "ai_task_configs", type_="check")
    op.create_check_constraint(
        "ck_ai_task_configs_task_type_values",
        "ai_task_configs",
        "task_type IN ('workout_plan_generation','body_photo_analysis','progress_comparison',"
        "'specialist_summary')",
    )
