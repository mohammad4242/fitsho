"""Add explicit profile equipment inventory.

Revision ID: 20260824_107
Revises: c0b1dd908291
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260824_107"
down_revision: str | Sequence[str] | None = "c0b1dd908291"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_profiles", sa.Column("available_equipment", sa.JSON(), nullable=True))
    op.drop_constraint(
        "ck_user_profiles_training_setup_consistency",
        "user_profiles",
        type_="check",
    )
    op.create_check_constraint(
        "ck_user_profiles_training_setup_consistency",
        "user_profiles",
        "(training_location = 'home' AND "
        "(home_training_setup IS NOT NULL OR available_equipment IS NOT NULL)) OR "
        "(training_location = 'gym' AND home_training_setup IS NULL)",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE user_profiles SET home_training_setup = 'bodyweight_only' "
        "WHERE training_location = 'home' AND home_training_setup IS NULL"
    )
    op.drop_constraint(
        "ck_user_profiles_training_setup_consistency",
        "user_profiles",
        type_="check",
    )
    op.create_check_constraint(
        "ck_user_profiles_training_setup_consistency",
        "user_profiles",
        "(training_location = 'home' AND home_training_setup IS NOT NULL) OR "
        "(training_location = 'gym' AND home_training_setup IS NULL)",
    )
    op.drop_column("user_profiles", "available_equipment")
