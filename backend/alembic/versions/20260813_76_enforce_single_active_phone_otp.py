"""enforce one active phone OTP challenge per number"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260813_76"
down_revision: str | Sequence[str] | None = "20260813_75"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_phone_otp_challenges_active_phone",
        "phone_otp_challenges",
        ["phone_number"],
        unique=True,
        postgresql_where=sa.text("consumed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_phone_otp_challenges_active_phone",
        table_name="phone_otp_challenges",
    )
