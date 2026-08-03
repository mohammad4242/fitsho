"""create versioned body progress comparisons"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_25"
down_revision: str | Sequence[str] | None = "20260803_24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "body_progress_comparisons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("previous_session_id", sa.Uuid(), nullable=False),
        sa.Column("current_session_id", sa.Uuid(), nullable=False),
        sa.Column("previous_result_version_id", sa.Uuid(), nullable=False),
        sa.Column("current_result_version_id", sa.Uuid(), nullable=False),
        sa.Column("previous_feedback_id", sa.Uuid(), nullable=True),
        sa.Column("current_feedback_id", sa.Uuid(), nullable=True),
        sa.Column("comparison_version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("normalized_result", sa.JSON(), nullable=False),
        sa.Column("quality_snapshot", sa.JSON(), nullable=False),
        sa.Column("context_snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "comparison_version > 0",
            name="ck_body_progress_comparisons_version_positive",
        ),
        sa.CheckConstraint(
            "previous_session_id <> current_session_id",
            name="ck_body_progress_comparisons_distinct_sessions",
        ),
        sa.CheckConstraint(
            "char_length(schema_version) > 0",
            name="ck_body_progress_comparisons_schema_version_present",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["previous_session_id"], ["body_photo_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["current_session_id"], ["body_photo_sessions.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["previous_result_version_id"],
            ["body_analysis_result_versions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["current_result_version_id"],
            ["body_analysis_result_versions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["previous_feedback_id"], ["workout_cycle_feedback.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["current_feedback_id"], ["workout_cycle_feedback.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "current_result_version_id",
            name="uq_body_progress_comparisons_current_result",
        ),
        sa.UniqueConstraint(
            "current_session_id",
            "comparison_version",
            name="uq_body_progress_comparisons_session_version",
        ),
    )
    op.create_index(
        "ix_body_progress_comparisons_user_id",
        "body_progress_comparisons",
        ["user_id"],
    )
    op.create_index(
        "ix_body_progress_comparisons_previous_session_id",
        "body_progress_comparisons",
        ["previous_session_id"],
    )
    op.create_index(
        "ix_body_progress_comparisons_current_session_id",
        "body_progress_comparisons",
        ["current_session_id"],
    )
    op.create_index(
        "ix_body_progress_comparisons_previous_result_version_id",
        "body_progress_comparisons",
        ["previous_result_version_id"],
    )
    op.create_index(
        "ix_body_progress_comparisons_current_result_version_id",
        "body_progress_comparisons",
        ["current_result_version_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_body_progress_comparisons_current_result_version_id",
        table_name="body_progress_comparisons",
    )
    op.drop_index(
        "ix_body_progress_comparisons_previous_result_version_id",
        table_name="body_progress_comparisons",
    )
    op.drop_index(
        "ix_body_progress_comparisons_current_session_id",
        table_name="body_progress_comparisons",
    )
    op.drop_index(
        "ix_body_progress_comparisons_previous_session_id",
        table_name="body_progress_comparisons",
    )
    op.drop_index(
        "ix_body_progress_comparisons_user_id",
        table_name="body_progress_comparisons",
    )
    op.drop_table("body_progress_comparisons")
