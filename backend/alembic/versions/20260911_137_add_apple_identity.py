"""add Apple authentication identity"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260911_137"
down_revision: str | Sequence[str] | None = "20260911_136"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("apple_sub", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_users_apple_sub", "users", ["apple_sub"])
    op.drop_constraint("ck_users_login_identifier_required", "users", type_="check")
    op.create_check_constraint(
        "ck_users_login_identifier_required",
        "users",
        "(email IS NOT NULL AND password_hash IS NOT NULL) "
        "OR phone_number IS NOT NULL OR google_sub IS NOT NULL OR apple_sub IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_login_identifier_required", "users", type_="check")
    op.drop_constraint("uq_users_apple_sub", "users", type_="unique")
    op.drop_column("users", "apple_sub")
    op.create_check_constraint(
        "ck_users_login_identifier_required",
        "users",
        "(email IS NOT NULL AND password_hash IS NOT NULL) "
        "OR phone_number IS NOT NULL OR google_sub IS NOT NULL",
    )
