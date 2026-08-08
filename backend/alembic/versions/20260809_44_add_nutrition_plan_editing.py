"""add nutrition plan editing, review, lab, and supplement foundations"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_44"
down_revision: str | Sequence[str] | None = "20260809_43"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_nutrition_plan_review_status_values",
        "nutrition_plan_physician_reviews",
        type_="check",
    )
    op.create_check_constraint(
        "ck_nutrition_plan_review_status_values",
        "nutrition_plan_physician_reviews",
        "status IN ('pending','in_review','awaiting_lab_information','changes_requested',"
        "'approved','rejected','invalidated_by_revision')",
    )
    op.add_column("nutrition_weekly_plans", sa.Column("supersedes_plan_id", sa.Uuid()))
    op.add_column("nutrition_weekly_plans", sa.Column("lineage_id", sa.Uuid()))
    op.create_foreign_key(
        "fk_nutrition_weekly_plans_supersedes",
        "nutrition_weekly_plans",
        "nutrition_weekly_plans",
        ["supersedes_plan_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute("UPDATE nutrition_weekly_plans SET lineage_id = id WHERE lineage_id IS NULL")
    op.alter_column("nutrition_weekly_plans", "lineage_id", nullable=False)
    op.create_index(
        "ix_nutrition_weekly_plans_supersedes_plan_id",
        "nutrition_weekly_plans",
        ["supersedes_plan_id"],
    )
    op.create_index(
        "ix_nutrition_weekly_plans_lineage_id", "nutrition_weekly_plans", ["lineage_id"]
    )
    op.add_column(
        "nutrition_weekly_plan_meals",
        sa.Column("is_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "nutrition_plan_physician_reviews", sa.Column("invalidated_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "nutrition_plan_physician_reviews", sa.Column("invalidation_reason", sa.String(64))
    )
    op.add_column(
        "nutrition_plan_physician_reviews", sa.Column("expected_plan_revision", sa.SmallInteger())
    )
    op.execute("""
        UPDATE nutrition_plan_physician_reviews r
        SET expected_plan_revision = p.revision
        FROM nutrition_weekly_plans p WHERE p.id = r.plan_id
    """)
    op.alter_column("nutrition_plan_physician_reviews", "expected_plan_revision", nullable=False)

    op.create_table(
        "nutrition_meal_feedback",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "meal_id",
            sa.Uuid(),
            sa.ForeignKey("nutrition_weekly_plan_meals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("feedback_type", sa.String(32), nullable=False),
        sa.Column("notes", sa.String(1000)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "meal_id", name="uq_nutrition_meal_feedback"),
        sa.CheckConstraint(
            "feedback_type IN ('liked','disliked','do_not_suggest_again',"
            "'prefer_more_often','too_large','too_small')",
            name="ck_nutrition_meal_feedback_type_values",
        ),
    )
    op.create_table(
        "nutrition_lab_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("storage_key", sa.String(500), nullable=False, unique=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column(
            "uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_nutrition_lab_documents_user_id", "nutrition_lab_documents", ["user_id"])
    op.create_table(
        "nutrition_lab_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "plan_id",
            sa.Uuid(),
            sa.ForeignKey("nutrition_weekly_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "physician_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("requested_tests", sa.JSON(), nullable=False),
        sa.Column("notes", sa.String(2000)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('requested','uploaded','reviewed','cancelled')",
            name="ck_nutrition_lab_request_status_values",
        ),
    )
    op.create_index("ix_nutrition_lab_requests_user_id", "nutrition_lab_requests", ["user_id"])
    op.create_table(
        "nutrition_supplement_orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "plan_id",
            sa.Uuid(),
            sa.ForeignKey("nutrition_weekly_plans.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "physician_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("dose", sa.String(160), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("nutrient_contribution", sa.JSON(), nullable=False),
        sa.Column("audit_metadata", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('draft','active','stopped')",
            name="ck_nutrition_supplement_order_status_values",
        ),
    )
    op.create_index(
        "ix_nutrition_supplement_orders_user_id", "nutrition_supplement_orders", ["user_id"]
    )


def downgrade() -> None:
    op.drop_table("nutrition_supplement_orders")
    op.drop_table("nutrition_lab_requests")
    op.drop_table("nutrition_lab_documents")
    op.drop_table("nutrition_meal_feedback")
    op.drop_column("nutrition_plan_physician_reviews", "expected_plan_revision")
    op.drop_column("nutrition_plan_physician_reviews", "invalidation_reason")
    op.drop_column("nutrition_plan_physician_reviews", "invalidated_at")
    op.drop_column("nutrition_weekly_plan_meals", "is_locked")
    op.drop_index("ix_nutrition_weekly_plans_lineage_id", table_name="nutrition_weekly_plans")
    op.drop_index(
        "ix_nutrition_weekly_plans_supersedes_plan_id", table_name="nutrition_weekly_plans"
    )
    op.drop_constraint(
        "fk_nutrition_weekly_plans_supersedes", "nutrition_weekly_plans", type_="foreignkey"
    )
    op.drop_column("nutrition_weekly_plans", "lineage_id")
    op.drop_column("nutrition_weekly_plans", "supersedes_plan_id")
    op.drop_constraint(
        "ck_nutrition_plan_review_status_values",
        "nutrition_plan_physician_reviews",
        type_="check",
    )
    op.create_check_constraint(
        "ck_nutrition_plan_review_status_values",
        "nutrition_plan_physician_reviews",
        "status IN ('pending','in_review','awaiting_lab_information','changes_requested',"
        "'approved','rejected')",
    )
