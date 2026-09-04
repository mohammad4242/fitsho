"""add plan bundles and generation roles"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260904_122"
down_revision: str | Sequence[str] | None = "20260904_121"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "nutrition_plan_bundles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("estimate_id", sa.Uuid(), nullable=True),
        sa.Column("comparison_snapshot", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["estimate_id"], ["nutrition_estimates.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_nutrition_plan_bundles_user_created",
        "nutrition_plan_bundles",
        ["user_id", "created_at"],
    )

    op.add_column(
        "nutrition_plan_generations",
        sa.Column("bundle_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "nutrition_plan_generations",
        sa.Column(
            "plan_role",
            sa.String(length=32),
            server_default="legacy",
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_nutrition_plan_generations_bundle_id",
        "nutrition_plan_generations",
        "nutrition_plan_bundles",
        ["bundle_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_nutrition_plan_generations_bundle_id",
        "nutrition_plan_generations",
        ["bundle_id"],
    )
    op.create_index(
        "uq_nutrition_plan_generations_bundle_role",
        "nutrition_plan_generations",
        ["bundle_id", "plan_role"],
        unique=True,
        postgresql_where=sa.text("bundle_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_nutrition_plan_generations_bundle_role",
        table_name="nutrition_plan_generations",
    )
    op.drop_index(
        "ix_nutrition_plan_generations_bundle_id",
        table_name="nutrition_plan_generations",
    )
    op.drop_constraint(
        "fk_nutrition_plan_generations_bundle_id",
        "nutrition_plan_generations",
        type_="foreignkey",
    )
    op.drop_column("nutrition_plan_generations", "plan_role")
    op.drop_column("nutrition_plan_generations", "bundle_id")
    op.drop_index(
        "ix_nutrition_plan_bundles_user_created",
        table_name="nutrition_plan_bundles",
    )
    op.drop_table("nutrition_plan_bundles")
