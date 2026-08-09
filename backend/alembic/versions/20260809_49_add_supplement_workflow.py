"""add physician managed supplement workflow"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_49"
down_revision: str | Sequence[str] | None = "20260809_48"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "nutrition_supplement_catalogue",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(120), nullable=False, unique=True),
        sa.Column("name_fa", sa.String(160), nullable=False),
        sa.Column("name_en", sa.String(160), nullable=False),
        sa.Column("verification_status", sa.String(24), nullable=False),
        sa.Column("source_name", sa.String(160), nullable=False),
        sa.Column("source_reference", sa.String(500), nullable=False),
        sa.Column("active_ingredients", sa.JSON(), nullable=False),
        sa.Column("nutrient_contribution_per_unit", sa.JSON(), nullable=False),
        sa.Column("contraindication_codes", sa.JSON(), nullable=False),
        sa.Column("allergen_codes", sa.JSON(), nullable=False),
        sa.Column("interaction_codes", sa.JSON(), nullable=False),
        sa.Column("upper_bound_rules", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "verification_status IN ('draft','verified','retired')",
            name="ck_nutrition_supplement_verification",
        ),
    )
    op.drop_constraint(
        "ck_nutrition_supplement_order_status_values", "nutrition_supplement_orders", type_="check"
    )
    op.execute(
        "UPDATE nutrition_supplement_orders SET status = 'discontinued' WHERE status = 'stopped'"
    )
    op.create_check_constraint(
        "ck_nutrition_supplement_order_status_values",
        "nutrition_supplement_orders",
        "status IN ('draft','prescribed','active','completed','discontinued','cancelled')",
    )
    columns = (
        sa.Column(
            "supplement_id",
            sa.Uuid(),
            sa.ForeignKey("nutrition_supplement_catalogue.id", ondelete="RESTRICT"),
        ),
        sa.Column("dose_amount", sa.Numeric(12, 4)),
        sa.Column("daily_units", sa.Numeric(12, 4)),
        sa.Column("dose_unit", sa.String(32)),
        sa.Column("frequency", sa.String(120)),
        sa.Column("duration_days", sa.SmallInteger()),
        sa.Column("starts_on", sa.Date()),
        sa.Column("ends_on", sa.Date()),
        sa.Column("instructions", sa.String(2000)),
        sa.Column("rationale", sa.String(2000)),
        sa.Column(
            "rationale_user_visible", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("linked_gap_codes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("linked_lab_document_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "follow_up_lab_request_id",
            sa.Uuid(),
            sa.ForeignKey("nutrition_lab_requests.id", ondelete="SET NULL"),
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("adherence_note", sa.String(1000)),
    )
    for column in columns:
        op.add_column("nutrition_supplement_orders", column)
    op.create_table(
        "nutrition_supplement_order_audits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey("nutrition_supplement_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("nutrition_supplement_order_audits")
    for name in (
        "adherence_note",
        "acknowledged_at",
        "follow_up_lab_request_id",
        "linked_lab_document_ids",
        "linked_gap_codes",
        "rationale_user_visible",
        "rationale",
        "instructions",
        "ends_on",
        "starts_on",
        "duration_days",
        "frequency",
        "dose_unit",
        "daily_units",
        "dose_amount",
        "supplement_id",
    ):
        op.drop_column("nutrition_supplement_orders", name)
    op.drop_constraint(
        "ck_nutrition_supplement_order_status_values", "nutrition_supplement_orders", type_="check"
    )
    op.execute(
        "UPDATE nutrition_supplement_orders SET status = 'stopped' "
        "WHERE status IN ('completed','discontinued','cancelled','prescribed')"
    )
    op.create_check_constraint(
        "ck_nutrition_supplement_order_status_values",
        "nutrition_supplement_orders",
        "status IN ('draft','active','stopped')",
    )
    op.drop_table("nutrition_supplement_catalogue")
