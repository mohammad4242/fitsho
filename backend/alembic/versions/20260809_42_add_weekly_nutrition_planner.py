"""add immutable scientific weekly nutrition planner"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_42"
down_revision: str | Sequence[str] | None = "20260808_41"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "nutrition_catalogue_foods",
        sa.Column(
            "dietary_patterns",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[\"omnivore\"]'::json"),
        ),
    )
    foods = sa.table(
        "nutrition_catalogue_foods",
        sa.column("slug", sa.String()),
        sa.column("dietary_patterns", sa.JSON()),
    )
    vegetarian_slugs = (
        "egg",
        "milk",
        "plain-yogurt",
        "low-fat-cheese",
        "butter",
    )
    omnivore_only_slugs = (
        "chicken-breast",
        "chicken-thigh-skinless",
        "beef",
        "lamb",
        "white-fish",
        "rainbow-trout",
        "canned-tuna",
        "grilled-chicken-breast",
    )
    op.execute(
        foods.update()
        .where(foods.c.slug.in_(vegetarian_slugs))
        .values(dietary_patterns=["omnivore", "vegetarian"])
    )
    op.execute(
        foods.update()
        .where(~foods.c.slug.in_((*vegetarian_slugs, *omnivore_only_slugs)))
        .values(dietary_patterns=["omnivore", "vegetarian", "vegan"])
    )
    op.create_table(
        "nutrition_planner_policy_versions",
        sa.Column("version", sa.String(64), primary_key=True),
        sa.Column("planner_version", sa.String(64), nullable=False),
        sa.Column("meal_distribution_policy", sa.JSON(), nullable=False),
        sa.Column("portion_policy", sa.JSON(), nullable=False),
        sa.Column("scoring_policy", sa.JSON(), nullable=False),
        sa.Column("tolerance_policy", sa.JSON(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.bulk_insert(
        sa.table(
            "nutrition_planner_policy_versions",
            sa.column("version", sa.String()),
            sa.column("planner_version", sa.String()),
            sa.column("meal_distribution_policy", sa.JSON()),
            sa.column("portion_policy", sa.JSON()),
            sa.column("scoring_policy", sa.JSON()),
            sa.column("tolerance_policy", sa.JSON()),
            sa.column("effective_at", sa.DateTime(timezone=True)),
        ),
        [
            {
                "version": "weekly-planner-v1",
                "planner_version": "deterministic-heuristic-v1",
                "meal_distribution_policy": {
                    "version": "meal-distribution-v1",
                    "snack_energy_share": "0.15",
                    "main_slots": [2, 3, 4],
                    "snack_slots": [0, 1, 2, 3],
                },
                "portion_policy": {
                    "version": "portion-bounds-v1",
                    "minimum_g": "10",
                    "maximum_main_food_g": "450",
                    "maximum_snack_food_g": "500",
                },
                "scoring_policy": {
                    "macro": {"method": "normalized_deviation", "weight": "hard_validation"},
                    "micronutrients": {"method": "adequacy_density", "weight": "4"},
                    "preference": {"weight": "1"},
                    "cost": {"method": "normalized_budget_deviation", "weight": "0.25"},
                    "repair_iterations": 3,
                },
                "tolerance_policy": {
                    "calorie_ratio": "0.20",
                    "macro_ratio": "0.10",
                    "micronutrient_data_completeness": "0.80",
                    "flexible_budget_overage_cap": "0.15",
                    "maximum_price_age_hours": 168,
                    "strict_budget_is_hard": True,
                },
                "effective_at": "2026-08-09T00:00:00+00:00",
            }
        ],
    )
    op.create_table(
        "nutrition_plan_generations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("estimate_id", sa.Uuid()),
        sa.Column("safety_decision_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("warning_codes", sa.JSON(), nullable=False),
        sa.Column("input_signature", sa.String(64), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("diagnostic_snapshot", sa.JSON(), nullable=False),
        sa.Column("planner_policy_version", sa.String(64), nullable=False),
        sa.Column("planner_version", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["estimate_id"], ["nutrition_estimates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["safety_decision_id"],
            ["nutrition_safety_decisions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["planner_policy_version"],
            ["nutrition_planner_policy_versions.version"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "outcome IN ('success', 'failed', 'safety_blocked', 'infeasible', "
            "'target_infeasible', 'live_price_unavailable')",
            name="ck_nutrition_plan_generation_outcome_values",
        ),
    )
    op.create_index(
        "ix_nutrition_plan_generations_user_created",
        "nutrition_plan_generations",
        ["user_id", "created_at"],
    )
    op.create_table(
        "nutrition_weekly_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("generation_id", sa.Uuid(), nullable=False),
        sa.Column("estimate_id", sa.Uuid(), nullable=False),
        sa.Column("safety_decision_id", sa.Uuid(), nullable=False),
        sa.Column("revision", sa.SmallInteger(), nullable=False),
        sa.Column("lifecycle_status", sa.String(48), nullable=False),
        sa.Column("is_user_visible", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("planner_policy_version", sa.String(64), nullable=False),
        sa.Column("planner_version", sa.String(64), nullable=False),
        sa.Column("scientific_policy_version", sa.String(64), nullable=False),
        sa.Column("formula_version", sa.String(64), nullable=False),
        sa.Column("food_data_manifest", sa.JSON(), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("price_snapshot", sa.JSON(), nullable=False),
        sa.Column("repair_snapshot", sa.JSON(), nullable=False),
        sa.Column("warning_codes", sa.JSON(), nullable=False),
        sa.Column("explanation_codes", sa.JSON(), nullable=False),
        sa.Column("weekly_cost_irr", sa.BigInteger(), nullable=False),
        sa.Column("weekly_budget_irr", sa.BigInteger(), nullable=False),
        sa.Column("budget_status", sa.String(24), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["nutrition_profiles.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["generation_id"], ["nutrition_plan_generations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["estimate_id"], ["nutrition_estimates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["safety_decision_id"],
            ["nutrition_safety_decisions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["planner_policy_version"],
            ["nutrition_planner_policy_versions.version"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("generation_id", name="uq_nutrition_weekly_plan_generation"),
        sa.UniqueConstraint("user_id", "revision", name="uq_nutrition_weekly_plan_user_revision"),
        sa.CheckConstraint("revision > 0", name="ck_nutrition_weekly_plan_revision_positive"),
        sa.CheckConstraint(
            "lifecycle_status IN ('draft', 'generated', 'pending_physician_review', "
            "'physician_review_in_progress', 'awaiting_lab_information', "
            "'changes_requested', 'physician_approved', 'active', 'archived', 'rejected')",
            name="ck_nutrition_weekly_plan_lifecycle_values",
        ),
        sa.CheckConstraint(
            "budget_status IN ('within_budget', 'flexible_overage', 'over_budget')",
            name="ck_nutrition_weekly_plan_budget_values",
        ),
    )
    op.create_index(
        "ix_nutrition_weekly_plans_user_created",
        "nutrition_weekly_plans",
        ["user_id", "created_at"],
    )
    op.create_table(
        "nutrition_weekly_plan_days",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("day_index", sa.SmallInteger(), nullable=False),
        sa.Column("plan_date", sa.Date(), nullable=False),
        sa.Column("cost_irr", sa.BigInteger(), nullable=False),
        sa.Column("nutrient_totals", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["nutrition_weekly_plans.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("plan_id", "day_index", name="uq_nutrition_weekly_plan_day"),
        sa.CheckConstraint("day_index BETWEEN 0 AND 6", name="ck_nutrition_weekly_plan_day_index"),
    )
    op.create_index(
        "ix_nutrition_weekly_plan_days_plan_id", "nutrition_weekly_plan_days", ["plan_id"]
    )
    op.create_table(
        "nutrition_weekly_plan_meals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("day_id", sa.Uuid(), nullable=False),
        sa.Column("slot_role", sa.String(16), nullable=False),
        sa.Column("slot_index", sa.SmallInteger(), nullable=False),
        sa.Column("target_distribution", sa.JSON(), nullable=False),
        sa.Column("nutrient_totals", sa.JSON(), nullable=False),
        sa.Column("cost_irr", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["day_id"], ["nutrition_weekly_plan_days.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "day_id", "slot_role", "slot_index", name="uq_nutrition_weekly_plan_meal_slot"
        ),
        sa.CheckConstraint("slot_index >= 0", name="ck_nutrition_weekly_plan_meal_slot_index"),
        sa.CheckConstraint(
            "slot_role IN ('main_meal', 'snack')",
            name="ck_nutrition_weekly_plan_meal_role_values",
        ),
    )
    op.create_index(
        "ix_nutrition_weekly_plan_meals_day_id", "nutrition_weekly_plan_meals", ["day_id"]
    )
    op.create_table(
        "nutrition_weekly_plan_foods",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("meal_id", sa.Uuid(), nullable=False),
        sa.Column("food_id", sa.Uuid(), nullable=False),
        sa.Column("food_slug", sa.String(120), nullable=False),
        sa.Column("food_name_fa", sa.String(160), nullable=False),
        sa.Column("food_name_en", sa.String(160), nullable=False),
        sa.Column("grams", sa.Numeric(20, 8), nullable=False),
        sa.Column("cost_irr", sa.BigInteger(), nullable=False),
        sa.Column("nutrient_snapshot", sa.JSON(), nullable=False),
        sa.Column("price_snapshot", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["meal_id"], ["nutrition_weekly_plan_meals.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["food_id"], ["nutrition_catalogue_foods.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("grams > 0", name="ck_nutrition_weekly_plan_food_grams_positive"),
        sa.CheckConstraint("cost_irr >= 0", name="ck_nutrition_weekly_plan_food_cost_nonnegative"),
    )
    op.create_index(
        "ix_nutrition_weekly_plan_foods_meal_id", "nutrition_weekly_plan_foods", ["meal_id"]
    )
    op.create_table(
        "nutrition_weekly_plan_nutrients",
        sa.Column("plan_id", sa.Uuid(), primary_key=True),
        sa.Column("nutrient_code", sa.String(48), primary_key=True),
        sa.Column("unit", sa.String(24), nullable=False),
        sa.Column("reference_kind", sa.String(24)),
        sa.Column("preferred_value", sa.Numeric(20, 8)),
        sa.Column("minimum_or_maximum_value", sa.Numeric(20, 8)),
        sa.Column("planned_value", sa.Numeric(20, 8), nullable=False),
        sa.Column("difference_from_preferred", sa.Numeric(20, 8)),
        sa.Column("difference_from_limit", sa.Numeric(20, 8)),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("data_confidence", sa.String(16), nullable=False),
        sa.Column("explanation_codes", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["nutrition_weekly_plans.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "nutrition_plan_physician_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("plan_id", sa.Uuid(), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("physician_user_id", sa.Uuid()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("user_visible_notes", sa.String(2000)),
        sa.ForeignKeyConstraint(["plan_id"], ["nutrition_weekly_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["physician_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "status IN ('pending', 'in_review', 'awaiting_lab_information', "
            "'changes_requested', 'approved', 'rejected')",
            name="ck_nutrition_plan_review_status_values",
        ),
    )


def downgrade() -> None:
    op.drop_table("nutrition_plan_physician_reviews")
    op.drop_table("nutrition_weekly_plan_nutrients")
    op.drop_index(
        "ix_nutrition_weekly_plan_foods_meal_id", table_name="nutrition_weekly_plan_foods"
    )
    op.drop_table("nutrition_weekly_plan_foods")
    op.drop_index("ix_nutrition_weekly_plan_meals_day_id", table_name="nutrition_weekly_plan_meals")
    op.drop_table("nutrition_weekly_plan_meals")
    op.drop_index("ix_nutrition_weekly_plan_days_plan_id", table_name="nutrition_weekly_plan_days")
    op.drop_table("nutrition_weekly_plan_days")
    op.drop_index("ix_nutrition_weekly_plans_user_created", table_name="nutrition_weekly_plans")
    op.drop_table("nutrition_weekly_plans")
    op.drop_index(
        "ix_nutrition_plan_generations_user_created",
        table_name="nutrition_plan_generations",
    )
    op.drop_table("nutrition_plan_generations")
    op.drop_table("nutrition_planner_policy_versions")
    op.drop_column("nutrition_catalogue_foods", "dietary_patterns")
