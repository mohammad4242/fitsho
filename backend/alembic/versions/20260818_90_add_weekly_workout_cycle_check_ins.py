"""add weekly workout cycle check-ins"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260818_90"
down_revision: str | Sequence[str] | None = "20260818_89"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workout_cycle_weekly_check_ins",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("cycle_id", sa.Uuid(), nullable=False),
        sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column("sessions_completed", sa.Integer(), nullable=False),
        sa.Column(
            "perceived_difficulty",
            sa.Enum(
                "too_easy",
                "easy",
                "appropriate",
                "hard",
                "too_hard",
                name="ck_workout_cycle_weekly_check_ins_difficulty_values",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "recovery_rating",
            sa.Enum(
                "good",
                "average",
                "poor",
                name="ck_workout_cycle_weekly_check_ins_recovery_values",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("has_pain_or_limitation", sa.Boolean(), nullable=False),
        sa.Column("note_optional", sa.Text(), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
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
        sa.CheckConstraint(
            "week_number >= 1",
            name="ck_workout_cycle_weekly_check_ins_week_positive",
        ),
        sa.CheckConstraint(
            "week_number <= 8",
            name="ck_workout_cycle_weekly_check_ins_week_max",
        ),
        sa.CheckConstraint(
            "sessions_completed >= 0",
            name="ck_weekly_check_ins_sessions_completed_nonnegative",
        ),
        sa.CheckConstraint(
            "sessions_completed <= 7",
            name="ck_workout_cycle_weekly_check_ins_sessions_completed_max",
        ),
        sa.CheckConstraint(
            "note_optional IS NULL OR char_length(note_optional) <= 2000",
            name="ck_workout_cycle_weekly_check_ins_note_length",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cycle_id"], ["workout_cycles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "cycle_id",
            "week_number",
            name="uq_workout_cycle_weekly_checkins_cycle_week",
        ),
    )
    op.create_index(
        "ix_workout_cycle_weekly_check_ins_user_cycle",
        "workout_cycle_weekly_check_ins",
        ["user_id", "cycle_id"],
    )
    op.create_index(
        "ix_workout_cycle_weekly_check_ins_cycle_week",
        "workout_cycle_weekly_check_ins",
        ["cycle_id", "week_number"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workout_cycle_weekly_check_ins_cycle_week",
        table_name="workout_cycle_weekly_check_ins",
    )
    op.drop_index(
        "ix_workout_cycle_weekly_check_ins_user_cycle",
        table_name="workout_cycle_weekly_check_ins",
    )
    op.drop_table("workout_cycle_weekly_check_ins")
