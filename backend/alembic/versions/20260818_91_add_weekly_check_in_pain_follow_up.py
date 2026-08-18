"""add structured weekly check-in pain follow-up"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260818_91"
down_revision: str | Sequence[str] | None = "20260818_90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workout_cycle_weekly_check_in_pain_limitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("weekly_check_in_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("cycle_id", sa.Uuid(), nullable=False),
        sa.Column("workout_plan_exercise_id", sa.Uuid(), nullable=False),
        sa.Column("note_optional", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "note_optional IS NULL OR char_length(note_optional) <= 500",
            name="ck_weekly_check_in_pain_followup_note_length",
        ),
        sa.ForeignKeyConstraint(
            ["weekly_check_in_id"],
            ["workout_cycle_weekly_check_ins.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cycle_id"], ["workout_cycles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["workout_plan_exercise_id"],
            ["workout_plan_exercises.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "weekly_check_in_id",
            name="uq_weekly_check_in_pain_followup_checkin",
        ),
    )
    op.create_index(
        "ix_weekly_check_in_pain_user_cycle",
        "workout_cycle_weekly_check_in_pain_limitations",
        ["user_id", "cycle_id"],
    )
    op.create_index(
        "ix_weekly_check_in_pain_cycle_exercise",
        "workout_cycle_weekly_check_in_pain_limitations",
        ["cycle_id", "workout_plan_exercise_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_weekly_check_in_pain_cycle_exercise",
        table_name="workout_cycle_weekly_check_in_pain_limitations",
    )
    op.drop_index(
        "ix_weekly_check_in_pain_user_cycle",
        table_name="workout_cycle_weekly_check_in_pain_limitations",
    )
    op.drop_table("workout_cycle_weekly_check_in_pain_limitations")
