"""add durable food photo analysis jobs"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260911_135"
down_revision: str | Sequence[str] | None = "20260910_134"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_nutrition_food_photo_status",
        "nutrition_food_photo_estimates",
        type_="check",
    )
    op.create_check_constraint(
        "ck_nutrition_food_photo_status",
        "nutrition_food_photo_estimates",
        "status IN ('queued','analyzing','estimated','confirmed','failed','deleted','expired')",
    )
    op.add_column(
        "nutrition_food_photo_estimates",
        sa.Column("error_code", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "nutrition_food_photo_estimates",
        sa.Column("error_message", sa.String(length=300), nullable=True),
    )
    op.create_table(
        "nutrition_food_photo_analysis_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "estimate_id",
            sa.Uuid(),
            sa.ForeignKey("nutrition_food_photo_estimates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=16), server_default="queued", nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=128), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("execution_config", sa.JSON(), nullable=False),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("last_error_message", sa.String(length=300), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('queued','processing','completed','failed')",
            name="ck_nutrition_food_photo_analysis_job_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND max_attempts BETWEEN 1 AND 10",
            name="ck_nutrition_food_photo_analysis_job_attempts",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("estimate_id"),
    )
    op.create_index(
        "ix_nutrition_food_photo_analysis_jobs_claim",
        "nutrition_food_photo_analysis_jobs",
        ["status", "available_at", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_nutrition_food_photo_analysis_jobs_claim",
        table_name="nutrition_food_photo_analysis_jobs",
    )
    op.drop_table("nutrition_food_photo_analysis_jobs")
    op.drop_column("nutrition_food_photo_estimates", "error_message")
    op.drop_column("nutrition_food_photo_estimates", "error_code")
    op.drop_constraint(
        "ck_nutrition_food_photo_status",
        "nutrition_food_photo_estimates",
        type_="check",
    )
    op.create_check_constraint(
        "ck_nutrition_food_photo_status",
        "nutrition_food_photo_estimates",
        "status IN ('estimated','confirmed','deleted','failed')",
    )
