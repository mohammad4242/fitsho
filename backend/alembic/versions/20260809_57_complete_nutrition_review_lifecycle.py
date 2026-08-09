"""complete nutrition physician review and laboratory lifecycle"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_57"
down_revision: str | Sequence[str] | None = "20260809_56"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "nutrition_lab_documents",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "nutrition_lab_documents",
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "nutrition_lab_documents",
        sa.Column("review_notes", sa.String(2000), nullable=True),
    )
    op.create_foreign_key(
        "fk_nutrition_lab_documents_reviewed_by_user_id",
        "nutrition_lab_documents",
        "users",
        ["reviewed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_nutrition_lab_documents_reviewed_by_user_id",
        "nutrition_lab_documents",
        ["reviewed_by_user_id"],
    )
    op.add_column(
        "nutrition_lab_requests",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "nutrition_lab_requests",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "uq_nutrition_weekly_plans_one_active_per_user",
        "nutrition_weekly_plans",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("lifecycle_status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_nutrition_weekly_plans_one_active_per_user",
        table_name="nutrition_weekly_plans",
        postgresql_using="btree",
    )
    op.drop_column("nutrition_lab_requests", "cancelled_at")
    op.drop_column("nutrition_lab_requests", "reviewed_at")
    op.drop_index(
        "ix_nutrition_lab_documents_reviewed_by_user_id",
        table_name="nutrition_lab_documents",
    )
    op.drop_constraint(
        "fk_nutrition_lab_documents_reviewed_by_user_id",
        "nutrition_lab_documents",
        type_="foreignkey",
    )
    op.drop_column("nutrition_lab_documents", "review_notes")
    op.drop_column("nutrition_lab_documents", "reviewed_by_user_id")
    op.drop_column("nutrition_lab_documents", "reviewed_at")
