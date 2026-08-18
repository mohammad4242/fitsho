"""persist real training age in user profiles"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260818_97"
down_revision: str | Sequence[str] | None = "20260818_96"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("training_age_months", sa.SmallInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_user_profiles_training_age_months_range",
        "user_profiles",
        "training_age_months BETWEEN 0 AND 900",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_user_profiles_training_age_months_range",
        "user_profiles",
        type_="check",
    )
    op.drop_column("user_profiles", "training_age_months")
