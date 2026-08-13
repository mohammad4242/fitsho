"""add password recovery and phone OTP authentication"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260813_75"
down_revision: str | Sequence[str] | None = "20260813_74"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("users", "email", existing_type=sa.String(length=320), nullable=True)
    op.alter_column("users", "password_hash", existing_type=sa.String(), nullable=True)
    op.add_column("users", sa.Column("phone_number", sa.String(length=13), nullable=True))
    op.create_unique_constraint("uq_users_phone_number", "users", ["phone_number"])
    op.create_check_constraint(
        "ck_users_login_identifier_required",
        "users",
        "email IS NOT NULL OR phone_number IS NOT NULL",
    )
    op.create_check_constraint(
        "ck_users_email_requires_password",
        "users",
        "email IS NULL OR password_hash IS NOT NULL",
    )

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_password_reset_tokens_user_id",
        "password_reset_tokens",
        ["user_id"],
    )

    op.create_table(
        "phone_otp_challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("phone_number", sa.String(length=13), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resend_available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts_remaining", sa.Integer(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attempts_remaining >= 0",
            name="ck_phone_otp_challenges_attempts_nonnegative",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_phone_otp_challenges_phone_number",
        "phone_otp_challenges",
        ["phone_number"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_phone_otp_challenges_phone_number",
        table_name="phone_otp_challenges",
    )
    op.drop_table("phone_otp_challenges")
    op.drop_index(
        "ix_password_reset_tokens_user_id",
        table_name="password_reset_tokens",
    )
    op.drop_table("password_reset_tokens")
    op.drop_constraint("ck_users_email_requires_password", "users", type_="check")
    op.drop_constraint("ck_users_login_identifier_required", "users", type_="check")
    op.drop_constraint("uq_users_phone_number", "users", type_="unique")
    op.drop_column("users", "phone_number")
    op.alter_column("users", "password_hash", existing_type=sa.String(), nullable=False)
    op.alter_column("users", "email", existing_type=sa.String(length=320), nullable=False)
