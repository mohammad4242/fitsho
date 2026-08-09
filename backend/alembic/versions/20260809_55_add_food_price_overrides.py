"""add audited temporary food price overrides"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_55"
down_revision: str | Sequence[str] | None = "20260809_54"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "nutrition_food_price_overrides",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("food_id", sa.Uuid(), nullable=False),
        sa.Column("reference_price_toman", sa.Numeric(20, 8), nullable=False),
        sa.Column("canonical_unit", sa.String(24), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expired_at", sa.DateTime(timezone=True)),
        sa.Column("expired_by_run_id", sa.Uuid()),
        sa.CheckConstraint(
            "reference_price_toman > 0", name="ck_nutrition_price_override_positive"
        ),
        sa.CheckConstraint(
            "canonical_unit IN ('TOMAN_PER_KG', 'TOMAN_PER_LITER', 'TOMAN_PER_UNIT')",
            name="ck_nutrition_price_override_unit_values",
        ),
        sa.CheckConstraint(
            "char_length(btrim(reason)) BETWEEN 5 AND 500",
            name="ck_nutrition_price_override_reason_length",
        ),
        sa.ForeignKeyConstraint(
            ["food_id"], ["nutrition_catalogue_foods.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["expired_by_run_id"],
            ["nutrition_food_price_update_runs.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_nutrition_food_price_overrides_food_id",
        "nutrition_food_price_overrides",
        ["food_id"],
    )
    op.create_index(
        "ix_nutrition_food_price_overrides_created_by_user_id",
        "nutrition_food_price_overrides",
        ["created_by_user_id"],
    )
    op.create_index(
        "ix_nutrition_food_price_overrides_expired_by_run_id",
        "nutrition_food_price_overrides",
        ["expired_by_run_id"],
    )
    op.create_index(
        "uq_nutrition_active_price_override_food",
        "nutrition_food_price_overrides",
        ["food_id"],
        unique=True,
        postgresql_where=sa.text("active"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_nutrition_active_price_override_food",
        table_name="nutrition_food_price_overrides",
        postgresql_using="btree",
    )
    op.drop_table("nutrition_food_price_overrides")
