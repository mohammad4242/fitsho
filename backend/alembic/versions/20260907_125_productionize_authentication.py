"""productionize authentication identities and verification"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260907_125"
down_revision: str | Sequence[str] | None = "20260905_124"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("google_sub", sa.String(length=255), nullable=True))
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_unique_constraint("uq_users_google_sub", "users", ["google_sub"])
    op.drop_constraint("ck_users_email_requires_password", "users", type_="check")
    op.drop_constraint("ck_users_login_identifier_required", "users", type_="check")
    op.create_check_constraint(
        "ck_users_login_identifier_required",
        "users",
        "(email IS NOT NULL AND password_hash IS NOT NULL) "
        "OR phone_number IS NOT NULL OR google_sub IS NOT NULL",
    )

    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_email_verification_tokens_token_hash"),
    )
    op.create_index(
        "ix_email_verification_tokens_user_id",
        "email_verification_tokens",
        ["user_id"],
    )

    op.create_table(
        "auth_operation_rate_limits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor_hash", sa.String(length=64), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.SmallInteger(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "actor_hash",
            "operation",
            "window_started_at",
            name="uq_auth_operation_rate_window",
        ),
    )
    op.create_index(
        "ix_auth_operation_rate_limits_actor_hash",
        "auth_operation_rate_limits",
        ["actor_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_auth_operation_rate_limits_actor_hash",
        table_name="auth_operation_rate_limits",
    )
    op.drop_table("auth_operation_rate_limits")
    op.drop_index(
        "ix_email_verification_tokens_user_id",
        table_name="email_verification_tokens",
    )
    op.drop_table("email_verification_tokens")

    op.drop_constraint("ck_users_login_identifier_required", "users", type_="check")
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
    op.drop_constraint("uq_users_google_sub", "users", type_="unique")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "google_sub")
