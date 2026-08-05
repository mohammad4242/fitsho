"""adjust profile body ranges"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260805_33"
down_revision: str | Sequence[str] | None = "20260805_32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_user_profiles_height_cm_range", "user_profiles")
    op.create_check_constraint(
        "ck_user_profiles_height_cm_range", "user_profiles", "height_cm BETWEEN 120 AND 230"
    )
    op.drop_constraint("ck_body_measurements_weight_kg_range", "body_measurements")
    op.create_check_constraint(
        "ck_body_measurements_weight_kg_range", "body_measurements", "weight_kg BETWEEN 35 AND 300"
    )


def downgrade() -> None:
    op.drop_constraint("ck_body_measurements_weight_kg_range", "body_measurements")
    op.create_check_constraint(
        "ck_body_measurements_weight_kg_range", "body_measurements", "weight_kg BETWEEN 20 AND 500"
    )
    op.drop_constraint("ck_user_profiles_height_cm_range", "user_profiles")
    op.create_check_constraint(
        "ck_user_profiles_height_cm_range", "user_profiles", "height_cm BETWEEN 100 AND 250"
    )
