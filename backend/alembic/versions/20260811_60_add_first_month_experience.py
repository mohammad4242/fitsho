"""add independent first-month training experience"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260811_60"
down_revision: str | Sequence[str] | None = "20260810_59"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_user_profiles_experience_level_values",
        "user_profiles",
        type_="check",
    )
    op.create_check_constraint(
        "ck_user_profiles_experience_level_values",
        "user_profiles",
        "experience_level IN ('first_month', 'beginner', 'intermediate', 'advanced')",
    )
    op.drop_constraint(
        "ck_training_program_templates_training_level_values",
        "training_program_templates",
        type_="check",
    )
    op.create_check_constraint(
        "ck_training_program_templates_training_level_values",
        "training_program_templates",
        "training_level IN ('first_month', 'beginner', 'intermediate', 'advanced')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_training_program_templates_training_level_values",
        "training_program_templates",
        type_="check",
    )
    op.create_check_constraint(
        "ck_training_program_templates_training_level_values",
        "training_program_templates",
        "training_level IN ('beginner', 'intermediate', 'advanced')",
    )
    op.drop_constraint(
        "ck_user_profiles_experience_level_values",
        "user_profiles",
        type_="check",
    )
    op.create_check_constraint(
        "ck_user_profiles_experience_level_values",
        "user_profiles",
        "experience_level IN ('beginner', 'intermediate', 'advanced')",
    )
