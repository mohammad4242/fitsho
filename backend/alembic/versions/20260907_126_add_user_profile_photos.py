"""add private user profile photos"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260907_126"
down_revision: str | Sequence[str] | None = "20260907_125"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_profile_photos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=32), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("width", sa.SmallInteger(), nullable=False),
        sa.Column("height", sa.SmallInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("byte_size > 0", name="ck_user_profile_photos_byte_size_positive"),
        sa.CheckConstraint(
            "width > 0 AND height > 0 AND width = height",
            name="ck_user_profile_photos_square_dimensions",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_user_profile_photos_storage_key"),
        sa.UniqueConstraint("user_id", name="uq_user_profile_photos_user_id"),
    )
    op.create_index(
        "ix_user_profile_photos_user_id",
        "user_profile_photos",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_profile_photos_user_id", table_name="user_profile_photos")
    op.drop_table("user_profile_photos")
