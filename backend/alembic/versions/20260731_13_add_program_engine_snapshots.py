"""add deterministic program engine snapshots

Revision ID: 20260731_13
Revises: 20260731_12
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260731_13"
down_revision: str | Sequence[str] | None = "20260731_12"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_workout_plan_generations_candidate_count_range",
        "workout_plan_generations",
        type_="check",
    )
    op.create_check_constraint(
        "ck_workout_plan_generations_candidate_count_range",
        "workout_plan_generations",
        "candidate_count BETWEEN 0 AND 5000",
    )
    op.add_column(
        "workout_plans",
        sa.Column(
            "engine_version",
            sa.String(length=64),
            server_default="legacy_ai",
            nullable=False,
        ),
    )
    op.add_column(
        "workout_plans",
        sa.Column("ruleset_version", sa.String(length=64), server_default="legacy", nullable=False),
    )
    op.add_column(
        "workout_plans",
        sa.Column(
            "primary_goal", sa.String(length=40), server_default="general_fitness", nullable=False
        ),
    )
    op.add_column("workout_plans", sa.Column("secondary_goal", sa.String(length=40), nullable=True))
    op.add_column(
        "workout_plans",
        sa.Column("training_status", sa.String(length=40), server_default="novice", nullable=False),
    )
    op.add_column(
        "workout_plans",
        sa.Column("safety_status", sa.String(length=50), server_default="clear", nullable=False),
    )
    op.add_column(
        "workout_plans",
        sa.Column("seed", sa.BigInteger(), server_default="0", nullable=False),
    )
    for column_name, default in (
        ("exercise_catalog_snapshot", "{}"),
        ("assumptions", "[]"),
        ("warnings", "[]"),
        ("validation_report", "{}"),
        ("aggregate_metrics", "{}"),
        ("decision_trace", "[]"),
        ("progression_policy", "{}"),
        ("difference_summary", "{}"),
    ):
        op.add_column(
            "workout_plans",
            sa.Column(
                column_name,
                sa.JSON(),
                server_default=sa.text(f"'{default}'::json"),
                nullable=False,
            ),
        )
    op.add_column(
        "workout_plans",
        sa.Column(
            "previous_program_id",
            sa.Uuid(),
            sa.ForeignKey("workout_plans.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "workout_plans", sa.Column("regeneration_reason", sa.String(length=160), nullable=True)
    )
    op.add_column(
        "workout_days",
        sa.Column("weekday", sa.SmallInteger(), nullable=True),
    )
    op.add_column(
        "workout_days",
        sa.Column("focus", sa.String(length=80), server_default="legacy", nullable=False),
    )
    op.add_column(
        "workout_days",
        sa.Column("cardio", sa.JSON(), nullable=True),
    )
    op.add_column(
        "workout_plan_exercises",
        sa.Column(
            "exercise_snapshot",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
    )
    op.add_column(
        "workout_plan_exercises",
        sa.Column("reason_codes", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False),
    )
    op.add_column(
        "workout_plan_exercises",
        sa.Column(
            "substitution_exercise_ids",
            sa.JSON(),
            server_default=sa.text("'[]'::json"),
            nullable=False,
        ),
    )
    op.add_column(
        "workout_plan_exercises",
        sa.Column("warmup_sets", sa.SmallInteger(), server_default="0", nullable=False),
    )
    op.add_column(
        "workout_plan_exercises",
        sa.Column("load_guidance", sa.Text(), server_default="", nullable=False),
    )
    op.add_column(
        "workout_plan_exercises",
        sa.Column(
            "progression_rule",
            sa.String(length=80),
            server_default="legacy",
            nullable=False,
        ),
    )


def downgrade() -> None:
    for column_name in (
        "progression_rule",
        "load_guidance",
        "warmup_sets",
        "substitution_exercise_ids",
        "reason_codes",
        "exercise_snapshot",
    ):
        op.drop_column("workout_plan_exercises", column_name)
    for column_name in ("cardio", "focus", "weekday"):
        op.drop_column("workout_days", column_name)
    for column_name in (
        "regeneration_reason",
        "previous_program_id",
        "difference_summary",
        "progression_policy",
        "decision_trace",
        "aggregate_metrics",
        "validation_report",
        "warnings",
        "assumptions",
        "exercise_catalog_snapshot",
        "seed",
        "ruleset_version",
        "safety_status",
        "training_status",
        "secondary_goal",
        "primary_goal",
        "engine_version",
    ):
        op.drop_column("workout_plans", column_name)
    op.drop_constraint(
        "ck_workout_plan_generations_candidate_count_range",
        "workout_plan_generations",
        type_="check",
    )
    op.create_check_constraint(
        "ck_workout_plan_generations_candidate_count_range",
        "workout_plan_generations",
        "candidate_count BETWEEN 0 AND 200",
    )
