"""add optional body circumference measurements"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260803_29"
down_revision: str | Sequence[str] | None = "20260803_28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "body_measurements", sa.Column("shoulder_circumference_cm", sa.Numeric(5, 2), nullable=True)
    )
    op.add_column(
        "body_measurements", sa.Column("waist_circumference_cm", sa.Numeric(5, 2), nullable=True)
    )
    op.add_column(
        "body_measurements", sa.Column("hip_circumference_cm", sa.Numeric(5, 2), nullable=True)
    )
    op.create_check_constraint(
        "ck_body_measurements_shoulder_circumference_range",
        "body_measurements",
        "shoulder_circumference_cm IS NULL OR shoulder_circumference_cm BETWEEN 40 AND 250",
    )
    op.create_check_constraint(
        "ck_body_measurements_waist_circumference_range",
        "body_measurements",
        "waist_circumference_cm IS NULL OR waist_circumference_cm BETWEEN 40 AND 250",
    )
    op.create_check_constraint(
        "ck_body_measurements_hip_circumference_range",
        "body_measurements",
        "hip_circumference_cm IS NULL OR hip_circumference_cm BETWEEN 40 AND 250",
    )


def downgrade() -> None:
    op.drop_constraint("ck_body_measurements_hip_circumference_range", "body_measurements")
    op.drop_constraint("ck_body_measurements_waist_circumference_range", "body_measurements")
    op.drop_constraint("ck_body_measurements_shoulder_circumference_range", "body_measurements")
    op.drop_column("body_measurements", "hip_circumference_cm")
    op.drop_column("body_measurements", "waist_circumference_cm")
    op.drop_column("body_measurements", "shoulder_circumference_cm")
