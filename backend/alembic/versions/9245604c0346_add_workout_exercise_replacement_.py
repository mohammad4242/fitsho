"""create workout exercise replacement tracking"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9245604c0346"
down_revision: str | Sequence[str] | None = "20260818_88"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workout_exercise_replacements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("cycle_id", sa.Uuid(), nullable=False),
        sa.Column("workout_plan_exercise_id", sa.Uuid(), nullable=False),
        sa.Column("original_exercise_id", sa.Uuid(), nullable=False),
        sa.Column("replacement_exercise_id", sa.Uuid(), nullable=False),
        sa.Column(
            "reason",
            sa.Enum(
                "equipment_unavailable",
                "uncomfortable",
                "pain_or_discomfort",
                "temporary_unavailable",
                "dislike",
                "other",
                name="ck_workout_exercise_replacements_reason_values",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "scope",
            sa.Enum(
                "this_time",
                "persistent",
                name="ck_workout_exercise_replacements_scope_values",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "original_exercise_id <> replacement_exercise_id",
            name="ck_workout_exercise_replacements_distinct_exercises",
        ),
        sa.CheckConstraint(
            "week_number BETWEEN 1 AND 8",
            name="ck_workout_exercise_replacements_week_number_range",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cycle_id"], ["workout_cycles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["workout_plan_exercise_id"],
            ["workout_plan_exercises.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["original_exercise_id"], ["exercises.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["replacement_exercise_id"], ["exercises.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workout_exercise_replacements_user_cycle",
        "workout_exercise_replacements",
        ["user_id", "cycle_id"],
    )
    op.create_index(
        "ix_workout_exercise_replacements_cycle_week",
        "workout_exercise_replacements",
        ["cycle_id", "week_number"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workout_exercise_replacements_cycle_week",
        table_name="workout_exercise_replacements",
    )
    op.drop_index(
        "ix_workout_exercise_replacements_user_cycle",
        table_name="workout_exercise_replacements",
    )
    op.drop_table("workout_exercise_replacements")
