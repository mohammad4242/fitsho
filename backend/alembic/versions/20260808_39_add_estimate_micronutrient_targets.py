"""persist selected micronutrient targets on scientific estimates"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260808_39"
down_revision: str | Sequence[str] | None = "20260808_38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "nutrition_estimate_micronutrient_targets",
        sa.Column("estimate_id", sa.Uuid(), nullable=False),
        sa.Column("nutrient_code", sa.String(length=48), nullable=False),
        sa.Column("reference_kind", sa.String(length=24), nullable=False),
        sa.Column("target_value", sa.Numeric(20, 8), nullable=False),
        sa.Column("unit", sa.String(length=24), nullable=False),
        sa.Column("unit_form", sa.String(length=48), nullable=False),
        sa.Column("upper_limit_value", sa.Numeric(20, 8)),
        sa.Column("upper_limit_kind", sa.String(length=24)),
        sa.Column("upper_limit_scope", sa.String(length=32), nullable=False),
        sa.Column("aggregation_window", sa.String(length=24), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("source_reference", sa.String(length=500), nullable=False),
        sa.Column("applicable_population", sa.String(length=200), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("explanation_codes", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["estimate_id"], ["nutrition_estimates.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("estimate_id", "nutrient_code"),
        sa.UniqueConstraint(
            "estimate_id", "nutrient_code", name="uq_nutrition_estimate_micro_nutrient"
        ),
        sa.CheckConstraint(
            "target_value >= 0", name="ck_nutrition_estimate_micro_target_nonnegative"
        ),
        sa.CheckConstraint(
            "upper_limit_value IS NULL OR upper_limit_value >= 0",
            name="ck_nutrition_estimate_micro_upper_nonnegative",
        ),
        sa.CheckConstraint(
            "confidence IN ('high', 'medium', 'low')",
            name="ck_nutrition_estimate_micro_confidence_values",
        ),
    )


def downgrade() -> None:
    op.drop_table("nutrition_estimate_micronutrient_targets")
