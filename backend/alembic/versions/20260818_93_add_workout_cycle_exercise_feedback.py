"""add structured workout cycle exercise feedback"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260818_93"
down_revision: str | Sequence[str] | None = "20260818_92"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workout_cycle_exercise_feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("cycle_id", sa.Uuid(), nullable=False),
        sa.Column("workout_plan_exercise_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column(
            "feedback_type",
            sa.Enum(
                "liked",
                "uncomfortable",
                "ineffective",
                "equipment_unavailable",
                "pain",
                name="ck_workout_cycle_exercise_feedback_type_values",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("persistent", sa.Boolean(), nullable=False),
        sa.Column("note_optional", sa.Text(), nullable=True),
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
            "note_optional IS NULL OR char_length(note_optional) <= 1000",
            name="ck_workout_cycle_exercise_feedback_note_length",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cycle_id"], ["workout_cycles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["workout_plan_exercise_id"],
            ["workout_plan_exercises.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "cycle_id",
            "workout_plan_exercise_id",
            "feedback_type",
            name="uq_workout_cycle_exercise_feedback_event",
        ),
    )
    op.create_index(
        "ix_workout_cycle_exercise_feedback_user_cycle",
        "workout_cycle_exercise_feedback",
        ["user_id", "cycle_id"],
    )
    op.create_index(
        "ix_workout_cycle_exercise_feedback_cycle_exercise",
        "workout_cycle_exercise_feedback",
        ["cycle_id", "workout_plan_exercise_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workout_cycle_exercise_feedback_cycle_exercise",
        table_name="workout_cycle_exercise_feedback",
    )
    op.drop_index(
        "ix_workout_cycle_exercise_feedback_user_cycle",
        table_name="workout_cycle_exercise_feedback",
    )
    op.drop_table("workout_cycle_exercise_feedback")
