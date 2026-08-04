"""add nutrition profile and safety foundation"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260805_31"
down_revision: str | Sequence[str] | None = "20260805_30"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def enum_check(column: str, values: tuple[str, ...]) -> sa.CheckConstraint:
    quoted = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({quoted})", name=f"ck_{column}_values")


def timestamps() -> tuple[sa.Column, sa.Column]:
    return (
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def upgrade() -> None:
    op.create_table(
        "medical_condition_policies",
        sa.Column("version", sa.String(length=64), primary_key=True),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.execute(
        sa.text(
            "INSERT INTO medical_condition_policies (version, description, effective_at) "
            "VALUES ('medical-condition-v1', "
            "'Task 0 approved adult nutrition safety classification', CURRENT_TIMESTAMP)"
        )
    )
    op.create_table(
        "nutrition_medical_profiles",
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("dangerous_food_reaction_history", sa.Boolean(), nullable=False),
        sa.Column("pregnant", sa.Boolean(), nullable=False),
        sa.Column("breastfeeding", sa.Boolean(), nullable=False),
        sa.Column("eating_disorder_diagnosed", sa.Boolean(), nullable=False),
        sa.Column("eating_disorder_active_symptoms", sa.Boolean(), nullable=False),
        sa.Column("emergency_or_danger_symptoms", sa.Boolean(), nullable=False),
        sa.Column("complex_medication_food_interaction", sa.Boolean(), nullable=False),
        sa.Column("physician_dietary_restrictions", sa.Text()),
        sa.Column("other_relevant_condition", sa.Text()),
        *timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.user_id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "physician_dietary_restrictions IS NULL OR "
            "char_length(physician_dietary_restrictions) <= 2000",
            name="ck_nutrition_medical_profiles_restrictions_length",
        ),
        sa.CheckConstraint(
            "other_relevant_condition IS NULL OR char_length(other_relevant_condition) <= 1000",
            name="ck_nutrition_medical_profiles_other_length",
        ),
    )
    op.create_table(
        "nutrition_medical_conditions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("details", sa.Text()),
        sa.ForeignKeyConstraint(
            ["user_id"], ["nutrition_medical_profiles.user_id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("user_id", "code", name="uq_nutrition_medical_conditions_user_code"),
        sa.CheckConstraint(
            "code IN ('controlled_hypertension', 'lipid_disorder', "
            "'type_2_diabetes_non_insulin', 'stable_gastrointestinal', 'kidney_disease', "
            "'dialysis', 'liver_disease', 'insulin_treated_diabetes', 'other')",
            name="ck_nutrition_medical_conditions_code_values",
        ),
        sa.CheckConstraint(
            "details IS NULL OR char_length(details) <= 1000",
            name="ck_nutrition_medical_conditions_details_length",
        ),
    )
    op.create_index(
        "ix_nutrition_medical_conditions_user_id",
        "nutrition_medical_conditions",
        ["user_id"],
    )
    op.create_table(
        "nutrition_medications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("dosage", sa.String(length=300)),
        sa.Column("notes", sa.Text()),
        sa.ForeignKeyConstraint(
            ["user_id"], ["nutrition_medical_profiles.user_id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "char_length(btrim(name)) BETWEEN 1 AND 160", name="ck_nutrition_medications_name"
        ),
        sa.CheckConstraint(
            "dosage IS NULL OR char_length(dosage) <= 300",
            name="ck_nutrition_medications_dosage",
        ),
        sa.CheckConstraint(
            "notes IS NULL OR char_length(notes) <= 1000", name="ck_nutrition_medications_notes"
        ),
    )
    op.create_index("ix_nutrition_medications_user_id", "nutrition_medications", ["user_id"])
    op.create_table(
        "nutrition_safety_decisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("medical_condition_policy_version", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["nutrition_medical_profiles.user_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["medical_condition_policy_version"],
            ["medical_condition_policies.version"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "outcome IN ('standard_automatic', "
            "'automatic_draft_requires_physician_review', "
            "'physician_manual_plan_required', 'unsupported_or_hard_blocked')",
            name="ck_nutrition_safety_decisions_outcome_values",
        ),
    )
    op.create_index(
        "ix_nutrition_safety_decisions_user_created",
        "nutrition_safety_decisions",
        ["user_id", "created_at"],
    )
    op.create_table(
        "nutrition_safety_reasons",
        sa.Column("safety_decision_id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(length=100), primary_key=True),
        sa.ForeignKeyConstraint(
            ["safety_decision_id"], ["nutrition_safety_decisions.id"], ondelete="CASCADE"
        ),
    )
    op.create_table(
        "nutrition_profiles",
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("onboarding_status", sa.String(length=24), nullable=False),
        sa.Column("individual_monthly_food_budget_irr", sa.BigInteger(), nullable=False),
        sa.Column("budget_style", sa.String(length=16), nullable=False),
        sa.Column("meals_per_day", sa.SmallInteger(), nullable=False),
        sa.Column("snacks_per_day", sa.SmallInteger(), nullable=False),
        sa.Column("preferred_plan_start_day", sa.String(length=16), nullable=False),
        sa.Column("plan_style", sa.String(length=16), nullable=False),
        sa.Column("cooking_skill", sa.String(length=16), nullable=False),
        sa.Column("maximum_cooking_time_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("cooking_frequency_per_week", sa.SmallInteger(), nullable=False),
        sa.Column("meal_preparation_preference", sa.String(length=16), nullable=False),
        sa.Column("refrigerator_access", sa.Boolean(), nullable=False),
        sa.Column("freezer_access", sa.Boolean(), nullable=False),
        sa.Column("supplied_meals_per_week", sa.SmallInteger(), nullable=False),
        sa.Column("supplied_meal_source", sa.String(length=300)),
        sa.Column("dietary_pattern", sa.String(length=16), nullable=False),
        sa.Column("preferred_variety", sa.String(length=16), nullable=False),
        sa.Column("maximum_meal_repetition_per_week", sa.SmallInteger(), nullable=False),
        sa.Column("accepts_leftovers", sa.Boolean(), nullable=False),
        sa.Column("accepts_batch_cooking", sa.Boolean(), nullable=False),
        sa.Column("work_shift_context", sa.String(length=500)),
        sa.Column("daily_check_in_enabled", sa.Boolean(), nullable=False),
        sa.Column("preferred_check_in_time", sa.Time()),
        *timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.user_id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "onboarding_status IN ('in_progress', 'completed')",
            name="ck_nutrition_profiles_status_values",
        ),
        sa.CheckConstraint(
            "individual_monthly_food_budget_irr BETWEEN 0 AND 100000000000",
            name="ck_nutrition_profiles_budget_range",
        ),
        sa.CheckConstraint(
            "budget_style IN ('strict', 'flexible')",
            name="ck_nutrition_profiles_budget_style_values",
        ),
        sa.CheckConstraint(
            "meals_per_day BETWEEN 1 AND 8", name="ck_nutrition_profiles_meals_range"
        ),
        sa.CheckConstraint(
            "snacks_per_day BETWEEN 0 AND 6", name="ck_nutrition_profiles_snacks_range"
        ),
        sa.CheckConstraint(
            "preferred_plan_start_day IN ('saturday', 'sunday', 'monday', 'tuesday', "
            "'wednesday', 'thursday', 'friday')",
            name="ck_nutrition_profiles_start_day_values",
        ),
        sa.CheckConstraint(
            "plan_style IN ('economical', 'balanced', 'simple')",
            name="ck_nutrition_profiles_plan_style_values",
        ),
        sa.CheckConstraint(
            "cooking_skill IN ('none', 'basic', 'confident')",
            name="ck_nutrition_profiles_cooking_skill_values",
        ),
        sa.CheckConstraint(
            "maximum_cooking_time_minutes BETWEEN 0 AND 360",
            name="ck_nutrition_profiles_cooking_time_range",
        ),
        sa.CheckConstraint(
            "cooking_frequency_per_week BETWEEN 0 AND 7",
            name="ck_nutrition_profiles_cooking_frequency_range",
        ),
        sa.CheckConstraint(
            "meal_preparation_preference IN ('daily', 'batch', 'mixed', 'no_cooking')",
            name="ck_nutrition_profiles_meal_prep_values",
        ),
        sa.CheckConstraint(
            "supplied_meals_per_week BETWEEN 0 AND 35",
            name="ck_nutrition_profiles_supplied_meals_range",
        ),
        sa.CheckConstraint(
            "dietary_pattern IN ('omnivore', 'vegetarian', 'vegan')",
            name="ck_nutrition_profiles_dietary_pattern_values",
        ),
        sa.CheckConstraint(
            "preferred_variety IN ('low', 'medium', 'high')",
            name="ck_nutrition_profiles_variety_values",
        ),
        sa.CheckConstraint(
            "maximum_meal_repetition_per_week BETWEEN 1 AND 7",
            name="ck_nutrition_profiles_repetition_range",
        ),
    )
    op.create_table(
        "nutrition_cooking_equipment",
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("equipment", sa.String(length=24), primary_key=True),
        sa.ForeignKeyConstraint(["user_id"], ["nutrition_profiles.user_id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "equipment IN ('stove', 'oven', 'microwave', 'air_fryer', 'rice_cooker', "
            "'blender', 'refrigerator')",
            name="ck_nutrition_cooking_equipment_values",
        ),
    )
    op.create_table(
        "nutrition_food_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("normalized_name", sa.String(length=120), nullable=False),
        sa.Column("details", sa.String(length=500)),
        sa.ForeignKeyConstraint(["user_id"], ["nutrition_profiles.user_id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "user_id", "kind", "normalized_name", name="uq_nutrition_food_items_user_kind_name"
        ),
        sa.CheckConstraint(
            "kind IN ('available_at_home', 'favourite', 'disliked', 'never_suggest', "
            "'refused', 'allergy', 'intolerance', 'religious_cultural_exclusion')",
            name="ck_nutrition_food_items_kind_values",
        ),
        sa.CheckConstraint(
            "char_length(btrim(name)) BETWEEN 1 AND 120", name="ck_nutrition_food_items_name"
        ),
        sa.CheckConstraint(
            "details IS NULL OR char_length(details) <= 500", name="ck_nutrition_food_items_details"
        ),
    )
    op.create_index(
        "ix_nutrition_food_items_kind_name",
        "nutrition_food_items",
        ["kind", "normalized_name"],
    )
    op.create_table(
        "nutrition_physician_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("safety_decision_id", sa.Uuid(), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("reviewer_id", sa.Uuid()),
        sa.Column("notes", sa.String(length=2000)),
        *timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["user_profiles.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["safety_decision_id"], ["nutrition_safety_decisions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "mode IN ('none', 'automatic_draft_review', 'manual_plan', 'blocked')",
            name="ck_nutrition_physician_reviews_mode_values",
        ),
        sa.CheckConstraint(
            "status IN ('not_requested', 'pending', 'approved', 'rejected', 'changes_requested')",
            name="ck_nutrition_physician_reviews_status_values",
        ),
    )
    op.create_index(
        "ix_nutrition_physician_reviews_user_id", "nutrition_physician_reviews", ["user_id"]
    )
    op.create_index(
        "ix_nutrition_physician_reviews_safety_decision_id",
        "nutrition_physician_reviews",
        ["safety_decision_id"],
    )


def downgrade() -> None:
    op.drop_table("nutrition_physician_reviews")
    op.drop_table("nutrition_food_items")
    op.drop_table("nutrition_cooking_equipment")
    op.drop_table("nutrition_profiles")
    op.drop_table("nutrition_safety_reasons")
    op.drop_table("nutrition_safety_decisions")
    op.drop_table("nutrition_medications")
    op.drop_table("nutrition_medical_conditions")
    op.drop_table("nutrition_medical_profiles")
    op.drop_table("medical_condition_policies")
