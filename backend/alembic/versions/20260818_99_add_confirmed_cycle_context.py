"""store explicit next-cycle context from end-of-cycle feedback"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260818_99"
down_revision: str | Sequence[str] | None = "20260818_98"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


LOCATION_VALUES = ("home", "gym")
HOME_SETUP_VALUES = ("bodyweight_only", "dumbbells_available")


def _enum_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.add_column(
        "workout_cycle_feedback",
        sa.Column("next_preferred_weekdays", sa.JSON(), nullable=True),
    )
    op.add_column(
        "workout_cycle_feedback",
        sa.Column(
            "next_training_location",
            sa.Enum(*LOCATION_VALUES, native_enum=False, create_constraint=False),
            nullable=True,
        ),
    )
    op.add_column(
        "workout_cycle_feedback",
        sa.Column(
            "next_home_training_setup",
            sa.Enum(*HOME_SETUP_VALUES, native_enum=False, create_constraint=False),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "ck_workout_cycle_feedback_next_training_location_values",
        "workout_cycle_feedback",
        "next_training_location IS NULL OR next_training_location IN "
        f"({_enum_values(LOCATION_VALUES)})",
    )
    op.create_check_constraint(
        "ck_workout_cycle_feedback_next_home_training_setup_values",
        "workout_cycle_feedback",
        "next_home_training_setup IS NULL OR next_home_training_setup IN "
        f"({_enum_values(HOME_SETUP_VALUES)})",
    )
    op.create_check_constraint(
        "ck_workout_cycle_feedback_next_training_setup_consistency",
        "workout_cycle_feedback",
        "next_training_location IS NULL OR "
        "(next_training_location = 'home' AND next_home_training_setup IS NOT NULL) OR "
        "(next_training_location = 'gym' AND next_home_training_setup IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_workout_cycle_feedback_next_training_setup_consistency",
        "workout_cycle_feedback",
        type_="check",
    )
    op.drop_constraint(
        "ck_workout_cycle_feedback_next_home_training_setup_values",
        "workout_cycle_feedback",
        type_="check",
    )
    op.drop_constraint(
        "ck_workout_cycle_feedback_next_training_location_values",
        "workout_cycle_feedback",
        type_="check",
    )
    op.drop_column("workout_cycle_feedback", "next_home_training_setup")
    op.drop_column("workout_cycle_feedback", "next_training_location")
    op.drop_column("workout_cycle_feedback", "next_preferred_weekdays")
