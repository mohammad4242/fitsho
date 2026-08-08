"""add low friction nutrition consumption tracking"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_45"
down_revision: str | Sequence[str] | None = "20260809_44"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "nutrition_daily_check_ins",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column(
            "plan_revision_id",
            sa.Uuid(),
            sa.ForeignKey("nutrition_weekly_plans.id", ondelete="RESTRICT"),
        ),
        sa.Column("note", sa.String(1000)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("user_id", "entry_date", name="uq_nutrition_daily_check_in"),
        sa.CheckConstraint(
            "status IN ('on_plan','mostly_on_plan','off_plan','not_recorded')",
            name="ck_nutrition_daily_check_in_status_values",
        ),
    )
    op.create_index(
        "ix_nutrition_daily_check_ins_user_id", "nutrition_daily_check_ins", ["user_id"]
    )
    op.create_table(
        "nutrition_consumption_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column(
            "plan_revision_id",
            sa.Uuid(),
            sa.ForeignKey("nutrition_weekly_plans.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "planned_meal_id",
            sa.Uuid(),
            sa.ForeignKey("nutrition_weekly_plan_meals.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "food_id",
            sa.Uuid(),
            sa.ForeignKey("nutrition_catalogue_foods.id", ondelete="RESTRICT"),
        ),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("quantity_grams", sa.Numeric(20, 8)),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("confidence", sa.String(16), nullable=False),
        sa.Column("user_confirmed", sa.Boolean(), nullable=False),
        sa.Column("nutrients", sa.JSON(), nullable=False),
        sa.Column("warning_codes", sa.JSON(), nullable=False),
        sa.Column("note", sa.String(1000)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "quantity_grams IS NULL OR quantity_grams > 0",
            name="ck_nutrition_consumption_quantity",
        ),
        sa.CheckConstraint(
            "source IN ('planned_confirmed','planned_adjusted','catalogue_manual',"
            "'photo_estimated_confirmed','photo_estimated_edited','quick_approximation',"
            "'professional_entry')",
            name="ck_nutrition_consumption_source_values",
        ),
        sa.CheckConstraint(
            "confidence IN ('high','medium','low')",
            name="ck_nutrition_consumption_confidence_values",
        ),
    )
    op.create_index(
        "ix_nutrition_consumption_user_date",
        "nutrition_consumption_entries",
        ["user_id", "entry_date"],
    )


def downgrade() -> None:
    op.drop_table("nutrition_consumption_entries")
    op.drop_table("nutrition_daily_check_ins")
