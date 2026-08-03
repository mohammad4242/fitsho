"""create versioned body analyses"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_19"
down_revision: str | Sequence[str] | None = "20260803_18b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "body_analyses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("replaces_analysis_id", sa.Uuid(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model_id", sa.String(length=300), nullable=False),
        sa.Column("fallback_model_id", sa.String(length=300), nullable=True),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "validating",
                "analyzing",
                "review_pending",
                "completed",
                "failed",
                name="ck_body_analyses_status_values",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("raw_result", sa.JSON(), nullable=True),
        sa.Column("normalized_result", sa.JSON(), nullable=True),
        sa.Column("overall_confidence", sa.Float(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("provider_request_id", sa.String(length=160), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("request_cost", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "attempt_count >= 0", name="ck_body_analyses_attempt_count_nonnegative"
        ),
        sa.CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_body_analyses_input_tokens_nonnegative",
        ),
        sa.CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_body_analyses_output_tokens_nonnegative",
        ),
        sa.CheckConstraint(
            "overall_confidence IS NULL OR "
            "(overall_confidence >= 0 AND overall_confidence <= 1)",
            name="ck_body_analyses_overall_confidence_range",
        ),
        sa.CheckConstraint("revision > 0", name="ck_body_analyses_revision_positive"),
        sa.CheckConstraint(
            "request_cost IS NULL OR request_cost >= 0",
            name="ck_body_analyses_request_cost_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["replaces_analysis_id"], ["body_analyses.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["body_photo_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "revision", name="uq_body_analyses_session_revision"),
    )
    op.create_index("ix_body_analyses_session_id", "body_analyses", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_body_analyses_session_id", table_name="body_analyses")
    op.drop_table("body_analyses")
