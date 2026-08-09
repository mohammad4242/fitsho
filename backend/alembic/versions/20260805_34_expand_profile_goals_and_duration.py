"""expand supported profile goals and workout duration"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260805_34"
down_revision: str | Sequence[str] | None = "20260805_33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GOALS = (
    "'lose_weight', 'gain_weight', 'fat_loss', 'build_muscle', "
    "'body_recomposition', 'improve_fitness', 'maintain_weight'"
)
_OLD_GOALS = "'lose_weight', 'build_muscle', 'improve_fitness', 'maintain_weight'"


def upgrade() -> None:
    op.alter_column("user_profiles", "fitness_goal", type_=sa.String(length=24))
    op.drop_constraint("ck_user_profiles_fitness_goal_values", "user_profiles")
    op.create_check_constraint(
        "ck_user_profiles_fitness_goal_values", "user_profiles", f"fitness_goal IN ({_GOALS})"
    )
    op.drop_constraint("ck_user_profiles_session_duration_values", "user_profiles")
    op.create_check_constraint(
        "ck_user_profiles_session_duration_values",
        "user_profiles",
        "session_duration_minutes IN (30, 45, 60, 75, 90, 120)",
    )
    op.drop_constraint(
        "ck_training_program_templates_fitness_goal_values", "training_program_templates"
    )
    op.create_check_constraint(
        "ck_training_program_templates_fitness_goal_values",
        "training_program_templates",
        f"fitness_goal IN ({_GOALS})",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_training_program_templates_fitness_goal_values", "training_program_templates"
    )
    op.create_check_constraint(
        "ck_training_program_templates_fitness_goal_values",
        "training_program_templates",
        f"fitness_goal IN ({_OLD_GOALS})",
    )
    op.drop_constraint("ck_user_profiles_session_duration_values", "user_profiles")
    op.create_check_constraint(
        "ck_user_profiles_session_duration_values",
        "user_profiles",
        "session_duration_minutes IN (30, 45, 60, 75, 90)",
    )
    op.drop_constraint("ck_user_profiles_fitness_goal_values", "user_profiles")
    op.create_check_constraint(
        "ck_user_profiles_fitness_goal_values", "user_profiles", f"fitness_goal IN ({_OLD_GOALS})"
    )
    op.alter_column("user_profiles", "fitness_goal", type_=sa.String(length=15))
