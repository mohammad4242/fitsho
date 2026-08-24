"""create workout cycles and optional completion feedback"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_20"
down_revision: str | Sequence[str] | None = "20260803_19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workout_cycles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("workout_plan_id", sa.Uuid(), nullable=False),
        sa.Column("duration_weeks", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "completed",
                name="ck_workout_cycles_status_values",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "duration_weeks IN (4, 6, 8)", name="ck_workout_cycles_duration_weeks_supported"
        ),
        sa.CheckConstraint(
            "(status = 'active' AND completed_at IS NULL) "
            "OR (status = 'completed' AND completed_at IS NOT NULL)",
            name="ck_workout_cycles_completion_state",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workout_plan_id"], ["workout_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workout_plan_id", name="uq_workout_cycles_workout_plan_id"),
    )
    op.create_index("ix_workout_cycles_user_id", "workout_cycles", ["user_id"])
    op.create_table(
        "workout_cycle_feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("cycle_id", sa.Uuid(), nullable=False),
        sa.Column("adherence_percent", sa.Integer(), nullable=True),
        sa.Column("performance_changes", sa.Text(), nullable=True),
        sa.Column("pain_or_limitation_feedback", sa.Text(), nullable=True),
        sa.Column("measurements", sa.JSON(), nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "adherence_percent IS NULL OR adherence_percent BETWEEN 0 AND 100",
            name="ck_workout_cycle_feedback_adherence_range",
        ),
        sa.ForeignKeyConstraint(["cycle_id"], ["workout_cycles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", name="uq_workout_cycle_feedback_cycle_id"),
    )


def downgrade() -> None:
    op.drop_table("workout_cycle_feedback")
    op.drop_index("ix_workout_cycles_user_id", table_name="workout_cycles")
    op.drop_table("workout_cycles")
