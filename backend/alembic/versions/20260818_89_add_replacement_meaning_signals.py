"""add durable replacement preferences and safety signals"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260818_89"
down_revision: str | Sequence[str] | None = "9245604c0346"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workout_exercise_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column(
            "preference_type",
            sa.Enum(
                "equipment_unavailable",
                "uncomfortable",
                "dislike",
                name="ck_workout_exercise_preferences_type_values",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("source_replacement_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["source_replacement_id"],
            ["workout_exercise_replacements.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "exercise_id",
            "preference_type",
            name="uq_workout_exercise_preferences_user_exercise_type",
        ),
    )
    op.create_index(
        "ix_workout_exercise_preferences_user",
        "workout_exercise_preferences",
        ["user_id"],
    )

    op.create_table(
        "workout_exercise_safety_signals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("cycle_id", sa.Uuid(), nullable=False),
        sa.Column("workout_plan_exercise_id", sa.Uuid(), nullable=False),
        sa.Column("original_exercise_id", sa.Uuid(), nullable=False),
        sa.Column("replacement_exercise_id", sa.Uuid(), nullable=False),
        sa.Column(
            "signal_type",
            sa.Enum(
                "pain_or_discomfort",
                name="ck_workout_exercise_safety_signals_type_values",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("week_number", sa.Integer(), nullable=False),
        sa.Column("source_replacement_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "week_number BETWEEN 1 AND 8",
            name="ck_workout_exercise_safety_signals_week_number_range",
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
        sa.ForeignKeyConstraint(
            ["source_replacement_id"],
            ["workout_exercise_replacements.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "cycle_id",
            "workout_plan_exercise_id",
            "replacement_exercise_id",
            "week_number",
            "signal_type",
            name="uq_workout_exercise_safety_signals_event",
        ),
        sa.UniqueConstraint(
            "source_replacement_id",
            name="uq_workout_exercise_safety_signals_source_replacement",
        ),
    )
    op.create_index(
        "ix_workout_exercise_safety_signals_user_cycle",
        "workout_exercise_safety_signals",
        ["user_id", "cycle_id"],
    )
    op.create_index(
        "ix_workout_exercise_safety_signals_cycle_week",
        "workout_exercise_safety_signals",
        ["cycle_id", "week_number"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_workout_exercise_safety_signals_cycle_week",
        table_name="workout_exercise_safety_signals",
    )
    op.drop_index(
        "ix_workout_exercise_safety_signals_user_cycle",
        table_name="workout_exercise_safety_signals",
    )
    op.drop_table("workout_exercise_safety_signals")
    op.drop_index(
        "ix_workout_exercise_preferences_user",
        table_name="workout_exercise_preferences",
    )
    op.drop_table("workout_exercise_preferences")
