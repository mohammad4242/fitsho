"""add structured end-of-cycle feedback"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260818_92"
down_revision: str | Sequence[str] | None = "20260818_91"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DIFFICULTY_VALUES = ("too_easy", "easy", "appropriate", "hard", "too_hard")
RECOVERY_VALUES = ("good", "average", "poor")
SATISFACTION_VALUES = (
    "very_dissatisfied",
    "dissatisfied",
    "neutral",
    "satisfied",
    "very_satisfied",
)
PROGRESS_VALUES = ("declined", "unchanged", "improved")
GOAL_VALUES = (
    "fat_loss",
    "hypertrophy",
    "strength",
    "muscle_gain",
    "body_recomposition",
    "general_fitness",
    "muscular_endurance",
)


def _enum_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.add_column(
        "workout_cycle_feedback",
        sa.Column(
            "overall_difficulty",
            sa.Enum(*DIFFICULTY_VALUES, native_enum=False, create_constraint=False),
            nullable=True,
        ),
    )
    op.add_column(
        "workout_cycle_feedback",
        sa.Column(
            "overall_recovery",
            sa.Enum(*RECOVERY_VALUES, native_enum=False, create_constraint=False),
            nullable=True,
        ),
    )
    op.add_column(
        "workout_cycle_feedback",
        sa.Column(
            "overall_satisfaction",
            sa.Enum(*SATISFACTION_VALUES, native_enum=False, create_constraint=False),
            nullable=True,
        ),
    )
    for column_name in (
        "strength_progress",
        "muscle_progress",
        "endurance_progress",
        "energy_progress",
    ):
        op.add_column(
            "workout_cycle_feedback",
            sa.Column(
                column_name,
                sa.Enum(*PROGRESS_VALUES, native_enum=False, create_constraint=False),
                nullable=True,
            ),
        )
    op.add_column(
        "workout_cycle_feedback",
        sa.Column("progressed_muscles", sa.JSON(), nullable=True),
    )
    op.add_column(
        "workout_cycle_feedback",
        sa.Column("lagging_muscles", sa.JSON(), nullable=True),
    )
    op.add_column(
        "workout_cycle_feedback",
        sa.Column("goal_changed", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "workout_cycle_feedback",
        sa.Column(
            "next_goal",
            sa.Enum(*GOAL_VALUES, native_enum=False, create_constraint=False),
            nullable=True,
        ),
    )
    op.add_column(
        "workout_cycle_feedback",
        sa.Column("schedule_changed", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "workout_cycle_feedback",
        sa.Column("next_training_days", sa.Integer(), nullable=True),
    )
    op.add_column(
        "workout_cycle_feedback",
        sa.Column("next_session_duration_minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "workout_cycle_feedback",
        sa.Column("equipment_changed", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "workout_cycle_feedback",
        sa.Column("new_limitation", sa.Text(), nullable=True),
    )
    op.add_column(
        "workout_cycle_feedback",
        sa.Column("note_optional", sa.Text(), nullable=True),
    )

    op.create_check_constraint(
        "ck_workout_cycle_feedback_difficulty_values",
        "workout_cycle_feedback",
        f"overall_difficulty IS NULL OR overall_difficulty IN ({_enum_values(DIFFICULTY_VALUES)})",
    )
    op.create_check_constraint(
        "ck_workout_cycle_feedback_recovery_values",
        "workout_cycle_feedback",
        f"overall_recovery IS NULL OR overall_recovery IN ({_enum_values(RECOVERY_VALUES)})",
    )
    op.create_check_constraint(
        "ck_workout_cycle_feedback_satisfaction_values",
        "workout_cycle_feedback",
        f"overall_satisfaction IS NULL OR overall_satisfaction IN ({_enum_values(SATISFACTION_VALUES)})",
    )
    for column_name in (
        "strength_progress",
        "muscle_progress",
        "endurance_progress",
        "energy_progress",
    ):
        op.create_check_constraint(
            f"ck_workout_cycle_feedback_{column_name}_values",
            "workout_cycle_feedback",
            f"{column_name} IS NULL OR {column_name} IN ({_enum_values(PROGRESS_VALUES)})",
        )
    op.create_check_constraint(
        "ck_workout_cycle_feedback_next_goal_values",
        "workout_cycle_feedback",
        f"next_goal IS NULL OR next_goal IN ({_enum_values(GOAL_VALUES)})",
    )
    op.create_check_constraint(
        "ck_workout_cycle_feedback_training_days_range",
        "workout_cycle_feedback",
        "next_training_days IS NULL OR next_training_days BETWEEN 2 AND 6",
    )
    op.create_check_constraint(
        "ck_workout_cycle_feedback_session_duration_values",
        "workout_cycle_feedback",
        "next_session_duration_minutes IS NULL OR next_session_duration_minutes IN "
        "(30, 45, 60, 75, 90, 120)",
    )
    op.create_check_constraint(
        "ck_workout_cycle_feedback_limitation_length",
        "workout_cycle_feedback",
        "new_limitation IS NULL OR char_length(new_limitation) <= 1000",
    )
    op.create_check_constraint(
        "ck_workout_cycle_feedback_note_length",
        "workout_cycle_feedback",
        "note_optional IS NULL OR char_length(note_optional) <= 4000",
    )


def downgrade() -> None:
    for constraint_name in (
        "ck_workout_cycle_feedback_note_length",
        "ck_workout_cycle_feedback_limitation_length",
        "ck_workout_cycle_feedback_session_duration_values",
        "ck_workout_cycle_feedback_training_days_range",
        "ck_workout_cycle_feedback_next_goal_values",
        "ck_workout_cycle_feedback_energy_progress_values",
        "ck_workout_cycle_feedback_endurance_progress_values",
        "ck_workout_cycle_feedback_muscle_progress_values",
        "ck_workout_cycle_feedback_strength_progress_values",
        "ck_workout_cycle_feedback_satisfaction_values",
        "ck_workout_cycle_feedback_recovery_values",
        "ck_workout_cycle_feedback_difficulty_values",
    ):
        op.drop_constraint(constraint_name, "workout_cycle_feedback", type_="check")
    for column_name in (
        "note_optional",
        "new_limitation",
        "equipment_changed",
        "next_session_duration_minutes",
        "next_training_days",
        "schedule_changed",
        "next_goal",
        "goal_changed",
        "lagging_muscles",
        "progressed_muscles",
        "energy_progress",
        "endurance_progress",
        "muscle_progress",
        "strength_progress",
        "overall_satisfaction",
        "overall_recovery",
        "overall_difficulty",
    ):
        op.drop_column("workout_cycle_feedback", column_name)
