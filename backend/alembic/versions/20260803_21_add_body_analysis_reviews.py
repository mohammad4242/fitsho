"""add versioned body-analysis specialist reviews"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_21"
down_revision: str | Sequence[str] | None = "20260803_20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "body_analysis_result_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("replaces_version_id", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "ai",
                "coach",
                "doctor",
                name="ck_body_analysis_result_versions_source_values",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("normalized_result", sa.JSON(), nullable=False),
        sa.Column("overall_confidence", sa.Float(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "overall_confidence >= 0 AND overall_confidence <= 1",
            name="ck_body_analysis_result_versions_confidence_range",
        ),
        sa.CheckConstraint("version > 0", name="ck_body_analysis_result_versions_version_positive"),
        sa.ForeignKeyConstraint(["analysis_id"], ["body_analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["replaces_version_id"],
            ["body_analysis_result_versions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "analysis_id",
            "version",
            name="uq_body_analysis_result_versions_analysis_version",
        ),
    )
    op.create_index(
        "ix_body_analysis_result_versions_analysis_id",
        "body_analysis_result_versions",
        ["analysis_id"],
    )
    op.create_table(
        "body_analysis_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_id", sa.Uuid(), nullable=False),
        sa.Column("result_version_id", sa.Uuid(), nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), nullable=False),
        sa.Column(
            "reviewer_role",
            sa.Enum(
                "coach",
                "doctor",
                name="ck_body_analysis_reviews_role_values",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "decision",
            sa.Enum(
                "approved",
                "changes_required",
                "rejected",
                name="ck_body_analysis_reviews_decision_values",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.String(length=2000), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "notes IS NULL OR char_length(notes) > 0",
            name="ck_body_analysis_reviews_notes_nonempty",
        ),
        sa.ForeignKeyConstraint(["analysis_id"], ["body_analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["result_version_id"],
            ["body_analysis_result_versions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_body_analysis_reviews_analysis_id", "body_analysis_reviews", ["analysis_id"]
    )
    op.create_index(
        "ix_body_analysis_reviews_result_version_id",
        "body_analysis_reviews",
        ["result_version_id"],
    )
    op.create_index(
        "ix_body_analysis_reviews_reviewer_id", "body_analysis_reviews", ["reviewer_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_body_analysis_reviews_reviewer_id", table_name="body_analysis_reviews")
    op.drop_index("ix_body_analysis_reviews_result_version_id", table_name="body_analysis_reviews")
    op.drop_index("ix_body_analysis_reviews_analysis_id", table_name="body_analysis_reviews")
    op.drop_table("body_analysis_reviews")
    op.drop_index(
        "ix_body_analysis_result_versions_analysis_id",
        table_name="body_analysis_result_versions",
    )
    op.drop_table("body_analysis_result_versions")
