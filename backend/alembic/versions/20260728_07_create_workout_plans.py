"""create_workout_plans

Revision ID: 20260728_07
Revises: 20260728_06
Create Date: 2026-07-28 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260728_07"
down_revision = "20260728_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WORKOUT_PLAN_STATUSES = ("generating", "active", "superseded", "failed")
WORKOUT_GENERATION_STATUSES = ("generating", "succeeded", "failed")


def quoted_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "workout_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=12), server_default="generating", nullable=False),
        sa.Column("generation_signature", sa.String(length=64), nullable=False),
        sa.Column("profile_snapshot", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model_id", sa.String(length=160), nullable=False),
        sa.Column("prompt_version", sa.String(length=64), nullable=False),
        sa.Column("generation_policy_version", sa.String(length=64), nullable=False),
        sa.Column("candidate_set_hash", sa.String(length=64), nullable=False),
        sa.Column("generation_method", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            f"status IN ({quoted_values(WORKOUT_PLAN_STATUSES)})",
            name="ck_workout_plans_status_values",
        ),
        sa.CheckConstraint(
            "char_length(generation_signature) = 64",
            name="ck_workout_plans_generation_signature_length",
        ),
        sa.CheckConstraint(
            "char_length(candidate_set_hash) = 64",
            name="ck_workout_plans_candidate_set_hash_length",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workout_plans_user_id", "workout_plans", ["user_id"])
    op.create_index(
        "uq_workout_plans_one_active_per_user",
        "workout_plans",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "workout_days",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workout_plan_id", sa.Uuid(), nullable=False),
        sa.Column("day_number", sa.SmallInteger(), nullable=False),
        sa.Column("title_en", sa.String(length=120), nullable=False),
        sa.Column("title_fa", sa.String(length=120), nullable=False),
        sa.Column("estimated_duration_minutes", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint("day_number >= 1", name="ck_workout_days_day_number_positive"),
        sa.CheckConstraint(
            "estimated_duration_minutes BETWEEN 1 AND 180",
            name="ck_workout_days_estimated_duration_range",
        ),
        sa.ForeignKeyConstraint(["workout_plan_id"], ["workout_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workout_plan_id", "day_number", name="uq_workout_days_plan_day"),
    )

    op.create_table(
        "workout_plan_exercises",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workout_day_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("order_index", sa.SmallInteger(), nullable=False),
        sa.Column("sets", sa.SmallInteger(), nullable=False),
        sa.Column("reps_min", sa.SmallInteger(), nullable=False),
        sa.Column("reps_max", sa.SmallInteger(), nullable=False),
        sa.Column("rest_seconds", sa.SmallInteger(), nullable=False),
        sa.Column("rir", sa.SmallInteger(), nullable=False),
        sa.Column("estimated_minutes", sa.SmallInteger(), nullable=False),
        sa.Column("notes_en", sa.Text(), nullable=True),
        sa.Column("notes_fa", sa.Text(), nullable=True),
        sa.CheckConstraint("order_index >= 1", name="ck_workout_plan_exercises_order_positive"),
        sa.CheckConstraint("sets BETWEEN 1 AND 10", name="ck_workout_plan_exercises_sets_range"),
        sa.CheckConstraint(
            "reps_min BETWEEN 1 AND 100 AND reps_max BETWEEN 1 AND 100 AND reps_min <= reps_max",
            name="ck_workout_plan_exercises_reps_range",
        ),
        sa.CheckConstraint(
            "rest_seconds BETWEEN 0 AND 600", name="ck_workout_plan_exercises_rest_range"
        ),
        sa.CheckConstraint("rir BETWEEN 0 AND 5", name="ck_workout_plan_exercises_rir_range"),
        sa.CheckConstraint(
            "estimated_minutes BETWEEN 1 AND 90",
            name="ck_workout_plan_exercises_estimated_minutes_range",
        ),
        sa.CheckConstraint(
            "notes_en IS NULL OR char_length(notes_en) <= 1000",
            name="ck_workout_plan_exercises_notes_en_length",
        ),
        sa.CheckConstraint(
            "notes_fa IS NULL OR char_length(notes_fa) <= 1000",
            name="ck_workout_plan_exercises_notes_fa_length",
        ),
        sa.ForeignKeyConstraint(["workout_day_id"], ["workout_days.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workout_day_id", "order_index", name="uq_workout_plan_exercises_day_order"
        ),
        sa.UniqueConstraint(
            "workout_day_id", "exercise_id", name="uq_workout_plan_exercises_day_exercise"
        ),
    )

    op.create_table(
        "workout_plan_generations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("workout_plan_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model_id", sa.String(length=160), nullable=False),
        sa.Column("provider_request_id", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=12), server_default="generating", nullable=False),
        sa.Column("candidate_count", sa.SmallInteger(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("safe_error_message", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            f"status IN ({quoted_values(WORKOUT_GENERATION_STATUSES)})",
            name="ck_workout_plan_generations_status_values",
        ),
        sa.CheckConstraint(
            "candidate_count BETWEEN 0 AND 200",
            name="ck_workout_plan_generations_candidate_count_range",
        ),
        sa.CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_workout_plan_generations_input_tokens_nonnegative",
        ),
        sa.CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_workout_plan_generations_output_tokens_nonnegative",
        ),
        sa.CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_workout_plan_generations_latency_nonnegative",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workout_plan_id"], ["workout_plans.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workout_plan_generations_user_id",
        "workout_plan_generations",
        ["user_id"],
    )
    op.create_index(
        "uq_workout_plan_generations_one_running_per_user",
        "workout_plan_generations",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'generating'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "uq_workout_plan_generations_one_running_per_user",
        table_name="workout_plan_generations",
    )
    op.drop_index("ix_workout_plan_generations_user_id", table_name="workout_plan_generations")
    op.drop_table("workout_plan_generations")
    op.drop_table("workout_plan_exercises")
    op.drop_table("workout_days")
    op.drop_index("uq_workout_plans_one_active_per_user", table_name="workout_plans")
    op.drop_index("ix_workout_plans_user_id", table_name="workout_plans")
    op.drop_table("workout_plans")
