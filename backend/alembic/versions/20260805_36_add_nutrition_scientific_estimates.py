"""add nutrition scientific estimates"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "20260805_36"
down_revision: str | Sequence[str] | None = "20260805_35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column("training_intensity", sa.String(length=16), nullable=True),
    )
    op.create_check_constraint(
        "ck_user_profiles_training_intensity_values",
        "user_profiles",
        "training_intensity IN ('light', 'moderate', 'vigorous')",
    )
    op.add_column(
        "nutrition_profiles",
        sa.Column("metabolic_basis", sa.String(length=24), nullable=True),
    )
    op.create_check_constraint(
        "ck_nutrition_profiles_metabolic_basis_values",
        "nutrition_profiles",
        "metabolic_basis IN ('female_coefficient', 'male_coefficient')",
    )
    op.create_table(
        "nutrition_policy_versions",
        sa.Column("version", sa.String(length=64), primary_key=True),
        sa.Column("formula_version", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.Column("source_manifest", sa.JSON(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    policy_table = sa.table(
        "nutrition_policy_versions",
        sa.column("version", sa.String()),
        sa.column("formula_version", sa.String()),
        sa.column("description", sa.String()),
        sa.column("source_manifest", sa.JSON()),
        sa.column("effective_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        policy_table,
        [
            {
                "version": "nutrition-science-v1",
                "formula_version": "mifflin-net-met-v1",
                "description": "Task 3 approved deterministic adult nutrition policy",
                "source_manifest": {
                    "mifflin": "PMID:2305711",
                    "who_healthy_diet": "2026-01-26",
                    "nasem_dri": "2005/2023",
                    "adult_compendium": "2024",
                    "older_adult_compendium": "2024",
                    "protein_morton": "PMID:28698222",
                    "protein_tagawa": "PMID:31794597",
                    "espen_adjusted_weight": "2022",
                },
                "effective_at": datetime.now(UTC),
            }
        ],
    )
    op.create_table(
        "nutrition_structured_exercises",
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("trains", sa.Boolean(), nullable=False),
        sa.Column("exercise_type", sa.String(length=16)),
        sa.Column("days_per_week", sa.SmallInteger()),
        sa.Column("minutes_per_session", sa.SmallInteger()),
        sa.Column("intensity", sa.String(length=16)),
        sa.Column("source", sa.String(length=24), nullable=False),
        sa.Column(
            "confirmed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["nutrition_profiles.user_id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "(trains = false AND exercise_type IS NULL AND days_per_week IS NULL "
            "AND minutes_per_session IS NULL AND intensity IS NULL) OR "
            "(trains = true AND exercise_type IS NOT NULL AND days_per_week IS NOT NULL "
            "AND minutes_per_session IS NOT NULL AND intensity IS NOT NULL)",
            name="ck_nutrition_structured_exercises_complete_when_training",
        ),
        sa.CheckConstraint(
            "exercise_type IN ('resistance', 'endurance', 'mixed', 'other')",
            name="ck_nutrition_structured_exercises_type_values",
        ),
        sa.CheckConstraint(
            "days_per_week IS NULL OR days_per_week BETWEEN 1 AND 7",
            name="ck_nutrition_structured_exercises_days_range",
        ),
        sa.CheckConstraint(
            "minutes_per_session IS NULL OR minutes_per_session BETWEEN 1 AND 360",
            name="ck_nutrition_structured_exercises_minutes_range",
        ),
        sa.CheckConstraint(
            "intensity IN ('light', 'moderate', 'vigorous')",
            name="ck_nutrition_structured_exercises_intensity_values",
        ),
        sa.CheckConstraint(
            "source IN ('user_reported', 'training_profile', 'active_fitsho_plan')",
            name="ck_nutrition_structured_exercises_source_values",
        ),
    )
    op.create_table(
        "nutrition_estimates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("safety_decision_id", sa.Uuid(), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("formula_version", sa.String(length=64), nullable=False),
        sa.Column("revision", sa.SmallInteger(), nullable=False),
        sa.Column("input_signature", sa.String(length=64), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("overall_confidence", sa.String(length=16), nullable=False),
        sa.Column("confidence_reasons", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["nutrition_profiles.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["safety_decision_id"], ["nutrition_safety_decisions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["policy_version"], ["nutrition_policy_versions.version"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("user_id", "revision", name="uq_nutrition_estimates_user_revision"),
        sa.UniqueConstraint(
            "user_id",
            "input_signature",
            "policy_version",
            name="uq_nutrition_estimates_user_signature_policy",
        ),
        sa.CheckConstraint("revision > 0", name="ck_nutrition_estimates_revision_positive"),
        sa.CheckConstraint(
            "char_length(input_signature) = 64",
            name="ck_nutrition_estimates_signature_length",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'review_required')",
            name="ck_nutrition_estimates_status_values",
        ),
        sa.CheckConstraint(
            "overall_confidence IN ('high', 'medium', 'low')",
            name="ck_nutrition_estimates_confidence_values",
        ),
    )
    op.create_index(
        "ix_nutrition_estimates_user_created",
        "nutrition_estimates",
        ["user_id", "created_at"],
    )
    metrics = (
        "'bmr', 'non_exercise_energy', 'exercise_energy', 'tdee', 'goal_calories', "
        "'protein', 'carbohydrate', 'total_fat', 'fibre', 'free_sugar', "
        "'added_sugar', 'saturated_fat', 'trans_fat', 'sodium'"
    )
    op.create_table(
        "nutrition_estimate_targets",
        sa.Column("estimate_id", sa.Uuid(), primary_key=True),
        sa.Column("metric", sa.String(length=32), primary_key=True),
        sa.Column("unit", sa.String(length=24), nullable=False),
        sa.Column("minimum_value", sa.Numeric(20, 8)),
        sa.Column("preferred_value", sa.Numeric(20, 8)),
        sa.Column("preferred_maximum_value", sa.Numeric(20, 8)),
        sa.Column("maximum_value", sa.Numeric(20, 8)),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("source_ids", sa.JSON(), nullable=False),
        sa.Column("applicable_population", sa.String(length=200), nullable=False),
        sa.Column("rounding_rule", sa.String(length=100), nullable=False),
        sa.Column("explanation_codes", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["estimate_id"], ["nutrition_estimates.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            f"metric IN ({metrics})",
            name="ck_nutrition_estimate_targets_metric_values",
        ),
        sa.CheckConstraint(
            "confidence IN ('high', 'medium', 'low')",
            name="ck_nutrition_estimate_targets_confidence_values",
        ),
        sa.CheckConstraint(
            "(minimum_value IS NULL OR minimum_value >= 0) AND "
            "(preferred_value IS NULL OR preferred_value >= 0) AND "
            "(preferred_maximum_value IS NULL OR preferred_maximum_value >= 0) AND "
            "(maximum_value IS NULL OR maximum_value >= 0)",
            name="ck_nutrition_estimate_targets_nonnegative",
        ),
    )


def downgrade() -> None:
    op.drop_table("nutrition_estimate_targets")
    op.drop_index("ix_nutrition_estimates_user_created", table_name="nutrition_estimates")
    op.drop_table("nutrition_estimates")
    op.drop_table("nutrition_structured_exercises")
    op.drop_table("nutrition_policy_versions")
    op.drop_constraint(
        "ck_nutrition_profiles_metabolic_basis_values",
        "nutrition_profiles",
        type_="check",
    )
    op.drop_column("nutrition_profiles", "metabolic_basis")
    op.drop_constraint(
        "ck_user_profiles_training_intensity_values",
        "user_profiles",
        type_="check",
    )
    op.drop_column("user_profiles", "training_intensity")
