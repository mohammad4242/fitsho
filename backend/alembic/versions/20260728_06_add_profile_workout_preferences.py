"""add_profile_workout_preferences

Revision ID: 20260728_06
Revises: ebb9a7de257f
Create Date: 2026-07-28 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260728_06"
down_revision = "ebb9a7de257f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TRAINING_CAUTIONS = ("lower_back", "knee", "shoulder", "neck", "wrist", "other")


def quoted_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "user_profiles",
        sa.Column("plan_duration_weeks", sa.SmallInteger(), server_default="4", nullable=False),
    )
    op.create_check_constraint(
        "ck_user_profiles_plan_duration_weeks_values",
        "user_profiles",
        "plan_duration_weeks IN (4, 6, 8)",
    )
    op.create_table(
        "user_profile_training_cautions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("caution", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "caution"),
        sa.CheckConstraint(
            f"caution IN ({quoted_values(TRAINING_CAUTIONS)})",
            name="ck_user_profile_training_cautions_values",
        ),
    )
    op.create_index(
        "ix_user_profile_training_cautions_caution",
        "user_profile_training_cautions",
        ["caution"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_user_profile_training_cautions_caution",
        table_name="user_profile_training_cautions",
    )
    op.drop_table("user_profile_training_cautions")
    op.drop_constraint(
        "ck_user_profiles_plan_duration_weeks_values",
        "user_profiles",
        type_="check",
    )
    op.drop_column("user_profiles", "plan_duration_weeks")
