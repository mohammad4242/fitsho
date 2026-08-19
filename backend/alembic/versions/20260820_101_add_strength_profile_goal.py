"""add strength as a profile and training template goal"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260820_101"
down_revision: str | Sequence[str] | None = "20260819_100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GOALS = (
    "'lose_weight', 'gain_weight', 'fat_loss', 'build_muscle', "
    "'body_recomposition', 'strength', 'improve_fitness', 'maintain_weight'"
)
_OLD_GOALS = (
    "'lose_weight', 'gain_weight', 'fat_loss', 'build_muscle', "
    "'body_recomposition', 'improve_fitness', 'maintain_weight'"
)


def upgrade() -> None:
    op.drop_constraint("ck_user_profiles_fitness_goal_values", "user_profiles")
    op.create_check_constraint(
        "ck_user_profiles_fitness_goal_values",
        "user_profiles",
        f"fitness_goal IN ({_GOALS})",
    )
    op.drop_constraint(
        "ck_training_program_templates_fitness_goal_values",
        "training_program_templates",
    )
    op.create_check_constraint(
        "ck_training_program_templates_fitness_goal_values",
        "training_program_templates",
        f"fitness_goal IN ({_GOALS})",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_training_program_templates_fitness_goal_values",
        "training_program_templates",
    )
    op.create_check_constraint(
        "ck_training_program_templates_fitness_goal_values",
        "training_program_templates",
        f"fitness_goal IN ({_OLD_GOALS})",
    )
    op.drop_constraint("ck_user_profiles_fitness_goal_values", "user_profiles")
    op.create_check_constraint(
        "ck_user_profiles_fitness_goal_values",
        "user_profiles",
        f"fitness_goal IN ({_OLD_GOALS})",
    )
