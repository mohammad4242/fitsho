"""add exercise media asset order

Revision ID: 6b8f1d2c4e90
Revises: f6e34c2a8b19
Create Date: 2026-07-30 11:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "6b8f1d2c4e90"
down_revision: str | Sequence[str] | None = "f6e34c2a8b19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "exercise_media_assets",
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
    )
    op.drop_constraint(
        "uq_exercise_media_assets_exercise_presentation_role",
        "exercise_media_assets",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_exercise_media_assets_exercise_presentation_role_order",
        "exercise_media_assets",
        ["exercise_id", "presentation", "role", "sort_order"],
    )
    op.create_check_constraint(
        "ck_exercise_media_assets_sort_order",
        "exercise_media_assets",
        "sort_order >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_exercise_media_assets_sort_order", "exercise_media_assets", type_="check"
    )
    op.drop_constraint(
        "uq_exercise_media_assets_exercise_presentation_role_order",
        "exercise_media_assets",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_exercise_media_assets_exercise_presentation_role",
        "exercise_media_assets",
        ["exercise_id", "presentation", "role"],
    )
    op.drop_column("exercise_media_assets", "sort_order")
