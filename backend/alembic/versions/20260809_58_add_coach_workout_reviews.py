"""add coach workout reviews"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_58"
down_revision: str | Sequence[str] | None = "20260809_57"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workout_plan_reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_plan_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "claimed",
                "approved",
                "superseded",
                name="ck_workout_plan_reviews_status_values",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("claimed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("lease_acquired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("coach_note", sa.String(length=2000), nullable=True),
        sa.Column("draft_payload", sa.JSON(), nullable=True),
        sa.Column("draft_revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("approved_plan_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "draft_revision > 0",
            name="ck_workout_plan_reviews_draft_revision_positive",
        ),
        sa.CheckConstraint(
            "coach_note IS NULL OR char_length(coach_note) <= 2000",
            name="ck_workout_plan_reviews_coach_note_length",
        ),
        sa.CheckConstraint(
            "(claimed_by_user_id IS NULL AND lease_acquired_at IS NULL "
            "AND lease_expires_at IS NULL) OR "
            "(claimed_by_user_id IS NOT NULL AND lease_acquired_at IS NOT NULL "
            "AND lease_expires_at IS NOT NULL)",
            name="ck_workout_plan_reviews_lease_fields_consistent",
        ),
        sa.CheckConstraint(
            "lease_expires_at IS NULL OR lease_expires_at > lease_acquired_at",
            name="ck_workout_plan_reviews_lease_range",
        ),
        sa.ForeignKeyConstraint(["approved_plan_id"], ["workout_plans.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["claimed_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_plan_id"], ["workout_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("approved_plan_id", name="uq_workout_plan_reviews_approved_plan_id"),
        sa.UniqueConstraint("source_plan_id", name="uq_workout_plan_reviews_source_plan_id"),
    )
    op.create_index(
        "ix_workout_plan_reviews_claimed_by_user_id",
        "workout_plan_reviews",
        ["claimed_by_user_id"],
    )
    op.create_index("ix_workout_plan_reviews_status", "workout_plan_reviews", ["status"])
    op.create_index("ix_workout_plan_reviews_user_id", "workout_plan_reviews", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_workout_plan_reviews_user_id", table_name="workout_plan_reviews")
    op.drop_index("ix_workout_plan_reviews_status", table_name="workout_plan_reviews")
    op.drop_index("ix_workout_plan_reviews_claimed_by_user_id", table_name="workout_plan_reviews")
    op.drop_table("workout_plan_reviews")
