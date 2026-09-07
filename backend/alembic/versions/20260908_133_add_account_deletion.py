"""add account deletion lifecycle and retention-safe user references"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260908_133"
down_revision: str | Sequence[str] | None = "20260908_132"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _replace_user_fk(
    table: str,
    column: str,
    constraint: str,
    *,
    nullable: bool | None,
    ondelete: str,
) -> None:
    op.drop_constraint(constraint, table_name=table, type_="foreignkey")
    if nullable is not None:
        op.alter_column(table, column, nullable=nullable)
    op.create_foreign_key(
        constraint,
        table,
        "users",
        [column],
        ["id"],
        ondelete=ondelete,
    )


def upgrade() -> None:
    op.create_table(
        "account_deletion_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("reauthenticated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("grace_period_ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('pending', 'cancelled', 'completed')",
            name="ck_account_deletion_requests_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_account_deletion_requests_user_id",
        "account_deletion_requests",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_account_deletion_requests_user_id_requested_at",
        "account_deletion_requests",
        ["user_id", "requested_at"],
        unique=False,
    )
    op.create_index(
        "ix_account_deletion_requests_pending_grace_period",
        "account_deletion_requests",
        ["status", "grace_period_ends_at"],
        unique=False,
    )

    _replace_user_fk(
        "body_analysis_reviews",
        "reviewer_id",
        "body_analysis_reviews_reviewer_id_fkey",
        nullable=True,
        ondelete="SET NULL",
    )
    _replace_user_fk(
        "workout_plan_reviews",
        "claimed_by_user_id",
        "workout_plan_reviews_claimed_by_user_id_fkey",
        nullable=None,
        ondelete="SET NULL",
    )
    _replace_user_fk(
        "nutrition_food_price_overrides",
        "created_by_user_id",
        "nutrition_food_price_overrides_created_by_user_id_fkey",
        nullable=True,
        ondelete="SET NULL",
    )
    _replace_user_fk(
        "nutrition_lab_requests",
        "physician_user_id",
        "nutrition_lab_requests_physician_user_id_fkey",
        nullable=True,
        ondelete="SET NULL",
    )
    _replace_user_fk(
        "nutrition_plan_physician_reviews",
        "physician_user_id",
        "nutrition_plan_physician_reviews_physician_user_id_fkey",
        nullable=None,
        ondelete="SET NULL",
    )
    _replace_user_fk(
        "nutrition_supplement_orders",
        "physician_user_id",
        "nutrition_supplement_orders_physician_user_id_fkey",
        nullable=True,
        ondelete="SET NULL",
    )
    _replace_user_fk(
        "nutrition_supplement_order_audits",
        "actor_user_id",
        "nutrition_supplement_order_audits_actor_user_id_fkey",
        nullable=True,
        ondelete="SET NULL",
    )
    _replace_user_fk(
        "nutrition_review_audit_events",
        "actor_user_id",
        "nutrition_review_audit_events_actor_user_id_fkey",
        nullable=True,
        ondelete="SET NULL",
    )
    _replace_user_fk(
        "nutrition_physician_reviews",
        "reviewer_id",
        "nutrition_physician_reviews_reviewer_id_fkey",
        nullable=None,
        ondelete="SET NULL",
    )


def downgrade() -> None:
    _replace_user_fk(
        "nutrition_physician_reviews",
        "reviewer_id",
        "nutrition_physician_reviews_reviewer_id_fkey",
        nullable=None,
        ondelete="RESTRICT",
    )
    _replace_user_fk(
        "nutrition_review_audit_events",
        "actor_user_id",
        "nutrition_review_audit_events_actor_user_id_fkey",
        nullable=False,
        ondelete="RESTRICT",
    )
    _replace_user_fk(
        "nutrition_supplement_order_audits",
        "actor_user_id",
        "nutrition_supplement_order_audits_actor_user_id_fkey",
        nullable=False,
        ondelete="RESTRICT",
    )
    _replace_user_fk(
        "nutrition_supplement_orders",
        "physician_user_id",
        "nutrition_supplement_orders_physician_user_id_fkey",
        nullable=False,
        ondelete="RESTRICT",
    )
    _replace_user_fk(
        "nutrition_lab_requests",
        "physician_user_id",
        "nutrition_lab_requests_physician_user_id_fkey",
        nullable=False,
        ondelete="RESTRICT",
    )
    _replace_user_fk(
        "nutrition_food_price_overrides",
        "created_by_user_id",
        "nutrition_food_price_overrides_created_by_user_id_fkey",
        nullable=False,
        ondelete="RESTRICT",
    )
    _replace_user_fk(
        "workout_plan_reviews",
        "claimed_by_user_id",
        "workout_plan_reviews_claimed_by_user_id_fkey",
        nullable=None,
        ondelete="RESTRICT",
    )
    _replace_user_fk(
        "body_analysis_reviews",
        "reviewer_id",
        "body_analysis_reviews_reviewer_id_fkey",
        nullable=False,
        ondelete="RESTRICT",
    )
    op.drop_index(
        "ix_account_deletion_requests_pending_grace_period",
        table_name="account_deletion_requests",
    )
    op.drop_index(
        "ix_account_deletion_requests_user_id_requested_at",
        table_name="account_deletion_requests",
    )
    op.drop_index("ix_account_deletion_requests_user_id", table_name="account_deletion_requests")
    op.drop_table("account_deletion_requests")
