"""add explicit specialist reviewer roles"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_24"
down_revision: str | Sequence[str] | None = "20260803_23"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_specialist_roles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "coach",
                "doctor",
                name="ck_user_specialist_roles_role_values",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role"),
    )


def downgrade() -> None:
    op.drop_table("user_specialist_roles")
