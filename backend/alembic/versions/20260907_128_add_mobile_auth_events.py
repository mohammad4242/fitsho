"""add native mobile authentication audit events"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260907_128"
down_revision: str | Sequence[str] | None = "20260907_127"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mobile_auth_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("family_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_data", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["family_id"], ["mobile_token_families.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mobile_auth_events_user_id_created_at",
        "mobile_auth_events",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_mobile_auth_events_family_id_created_at",
        "mobile_auth_events",
        ["family_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_mobile_auth_events_family_id_created_at",
        table_name="mobile_auth_events",
    )
    op.drop_index(
        "ix_mobile_auth_events_user_id_created_at",
        table_name="mobile_auth_events",
    )
    op.drop_table("mobile_auth_events")
