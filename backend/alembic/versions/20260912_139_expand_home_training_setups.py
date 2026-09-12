"""expand home training presets and normalize existing home profiles"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260912_139"
down_revision: str | Sequence[str] | None = "20260911_138"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HOME_SETUP_VALUES = (
    "bodyweight_only",
    "dumbbells_available",
    "resistance_bands_available",
    "dumbbells_and_resistance_bands_available",
)
LEGACY_HOME_SETUP_VALUES = ("bodyweight_only", "dumbbells_available")


def _enum_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _drop_setup_constraints() -> None:
    op.drop_constraint(
        "ck_user_profiles_home_training_setup_values",
        "user_profiles",
        type_="check",
    )
    op.drop_constraint(
        "ck_workout_cycle_feedback_next_home_training_setup_values",
        "workout_cycle_feedback",
        type_="check",
    )


def _create_setup_constraints(values: tuple[str, ...]) -> None:
    op.create_check_constraint(
        "ck_user_profiles_home_training_setup_values",
        "user_profiles",
        "home_training_setup IS NULL OR home_training_setup IN "
        f"({_enum_values(values)})",
    )
    op.create_check_constraint(
        "ck_workout_cycle_feedback_next_home_training_setup_values",
        "workout_cycle_feedback",
        "next_home_training_setup IS NULL OR next_home_training_setup IN "
        f"({_enum_values(values)})",
    )


def _normalize_home_profiles() -> None:
    op.execute(
        """
        UPDATE user_profiles
        SET home_training_setup = CASE
            WHEN COALESCE(available_equipment::jsonb, '[]'::jsonb)
                @> '["dumbbell", "resistance_band"]'::jsonb
                THEN 'dumbbells_and_resistance_bands_available'
            WHEN COALESCE(available_equipment::jsonb, '[]'::jsonb)
                @> '["resistance_band"]'::jsonb
                THEN 'resistance_bands_available'
            WHEN COALESCE(available_equipment::jsonb, '[]'::jsonb)
                @> '["dumbbell"]'::jsonb
                THEN 'dumbbells_available'
            ELSE 'bodyweight_only'
        END
        WHERE training_location = 'home'
          AND home_training_setup IS NULL
        """
    )
    op.execute(
        """
        UPDATE user_profiles
        SET available_equipment = CASE home_training_setup
            WHEN 'bodyweight_only' THEN '["bodyweight", "pull_up_bar"]'::json
            WHEN 'dumbbells_available'
                THEN '["bodyweight", "dumbbell", "pull_up_bar"]'::json
            WHEN 'resistance_bands_available'
                THEN '["bodyweight", "resistance_band", "pull_up_bar"]'::json
            WHEN 'dumbbells_and_resistance_bands_available'
                THEN '["bodyweight", "dumbbell", "resistance_band", "pull_up_bar"]'::json
            ELSE available_equipment
        END
        WHERE training_location = 'home'
        """
    )


def _downgrade_home_profiles() -> None:
    op.execute(
        """
        UPDATE user_profiles
        SET home_training_setup = CASE home_training_setup
            WHEN 'resistance_bands_available' THEN 'bodyweight_only'
            WHEN 'dumbbells_and_resistance_bands_available' THEN 'dumbbells_available'
            ELSE home_training_setup
        END
        WHERE training_location = 'home'
        """
    )
    op.execute(
        """
        UPDATE user_profiles
        SET available_equipment = CASE home_training_setup
            WHEN 'bodyweight_only' THEN '["bodyweight", "pull_up_bar"]'::json
            WHEN 'dumbbells_available'
                THEN '["bodyweight", "dumbbell", "pull_up_bar"]'::json
            ELSE available_equipment
        END
        WHERE training_location = 'home'
        """
    )


def upgrade() -> None:
    _drop_setup_constraints()
    op.alter_column(
        "user_profiles",
        "home_training_setup",
        existing_type=sa.String(length=19),
        type_=sa.String(length=64),
        existing_nullable=True,
    )
    op.alter_column(
        "workout_cycle_feedback",
        "next_home_training_setup",
        existing_type=sa.String(length=19),
        type_=sa.String(length=64),
        existing_nullable=True,
    )
    _normalize_home_profiles()
    _create_setup_constraints(HOME_SETUP_VALUES)


def downgrade() -> None:
    _drop_setup_constraints()
    op.execute(
        """
        UPDATE workout_cycle_feedback
        SET next_home_training_setup = CASE next_home_training_setup
            WHEN 'resistance_bands_available' THEN 'bodyweight_only'
            WHEN 'dumbbells_and_resistance_bands_available' THEN 'dumbbells_available'
            ELSE next_home_training_setup
        END
        """
    )
    _downgrade_home_profiles()
    op.alter_column(
        "user_profiles",
        "home_training_setup",
        existing_type=sa.String(length=64),
        type_=sa.String(length=19),
        existing_nullable=True,
    )
    op.alter_column(
        "workout_cycle_feedback",
        "next_home_training_setup",
        existing_type=sa.String(length=64),
        type_=sa.String(length=19),
        existing_nullable=True,
    )
    _create_setup_constraints(LEGACY_HOME_SETUP_VALUES)
