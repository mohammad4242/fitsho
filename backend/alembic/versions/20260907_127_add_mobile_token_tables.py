"""add native mobile token families and opaque tokens"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260907_127"
down_revision: str | Sequence[str] | None = "20260907_126"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mobile_token_families",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("app_version", sa.String(length=64), nullable=False),
        sa.Column("device_name", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "char_length(btrim(device_id)) BETWEEN 1 AND 128",
            name="ck_mobile_token_families_device_id_length",
        ),
        sa.CheckConstraint(
            "platform IN ('android', 'ios')",
            name="ck_mobile_token_families_platform",
        ),
        sa.CheckConstraint(
            "char_length(btrim(app_version)) BETWEEN 1 AND 64",
            name="ck_mobile_token_families_app_version_length",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mobile_token_families_user_id_created_at",
        "mobile_token_families",
        ["user_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "mobile_access_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["mobile_token_families.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_mobile_access_tokens_token_hash"),
    )
    op.create_index(
        "ix_mobile_access_tokens_family_id_expires_at",
        "mobile_access_tokens",
        ["family_id", "expires_at"],
        unique=False,
    )

    op.create_table(
        "mobile_refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["family_id"],
            ["mobile_token_families.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["replaced_by_id"],
            ["mobile_refresh_tokens.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_mobile_refresh_tokens_token_hash"),
    )
    op.create_index(
        "ix_mobile_refresh_tokens_family_id_expires_at",
        "mobile_refresh_tokens",
        ["family_id", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mobile_refresh_tokens_family_id_expires_at",
        table_name="mobile_refresh_tokens",
    )
    op.drop_table("mobile_refresh_tokens")
    op.drop_index(
        "ix_mobile_access_tokens_family_id_expires_at",
        table_name="mobile_access_tokens",
    )
    op.drop_table("mobile_access_tokens")
    op.drop_index(
        "ix_mobile_token_families_user_id_created_at",
        table_name="mobile_token_families",
    )
    op.drop_table("mobile_token_families")
