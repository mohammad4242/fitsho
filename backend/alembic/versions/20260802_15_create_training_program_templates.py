"""create training program templates"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "20260802_15"
down_revision = "20260801_14"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "training_program_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("name_en", sa.String(length=160), nullable=False),
        sa.Column("name_fa", sa.String(length=160), nullable=False),
        sa.Column("description_en", sa.String(length=1000), nullable=False),
        sa.Column("description_fa", sa.String(length=1000), nullable=False),
        sa.Column("days_per_week", sa.Integer(), nullable=False),
        sa.Column("training_level", sa.String(length=12), nullable=False),
        sa.Column("fitness_goal", sa.String(length=20), nullable=False),
        sa.Column("focus_tags", sa.JSON(), nullable=False),
        sa.Column("intensity_methods", sa.JSON(), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.CheckConstraint(
            "days_per_week BETWEEN 2 AND 6", name="ck_training_program_templates_days_per_week"
        ),
        sa.CheckConstraint(
            "fitness_goal IN ('lose_weight', 'build_muscle', 'improve_fitness', 'maintain_weight')",
            name="ck_training_program_templates_fitness_goal_values",
        ),
        sa.CheckConstraint(
            "slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'",
            name="ck_training_program_templates_slug_format",
        ),
        sa.CheckConstraint(
            "training_level IN ('beginner', 'intermediate', 'advanced')",
            name="ck_training_program_templates_training_level_values",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_training_program_templates_slug"),
    )
    op.create_index(
        "ix_training_program_templates_days_per_week",
        "training_program_templates",
        ["days_per_week"],
    )
    op.create_table(
        "training_program_template_days",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("template_id", sa.Uuid(), nullable=False),
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.Column("title_en", sa.String(length=160), nullable=False),
        sa.Column("title_fa", sa.String(length=160), nullable=False),
        sa.Column("direct_target_muscles", sa.JSON(), nullable=False),
        sa.CheckConstraint("day_number >= 1", name="ck_training_program_template_days_day_number"),
        sa.ForeignKeyConstraint(
            ["template_id"], ["training_program_templates.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "template_id", "day_number", name="uq_training_program_template_days_template_day"
        ),
    )
    op.create_table(
        "training_program_template_slots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("template_day_id", sa.Uuid(), nullable=False),
        sa.Column("slot_order", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=True),
        sa.Column("exercise_slug_hint", sa.String(length=120), nullable=False),
        sa.Column("placeholder_name_en", sa.String(length=160), nullable=True),
        sa.Column("placeholder_name_fa", sa.String(length=160), nullable=True),
        sa.Column("target_muscles", sa.JSON(), nullable=False),
        sa.Column("movement_pattern", sa.String(length=32), nullable=False),
        sa.Column("intensity_method", sa.String(length=12), nullable=False),
        sa.Column("sets", sa.Integer(), nullable=False),
        sa.Column("rep_min", sa.Integer(), nullable=False),
        sa.Column("rep_max", sa.Integer(), nullable=False),
        sa.Column("target_rir", sa.Integer(), nullable=False),
        sa.Column("rest_seconds", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "intensity_method IN ('standard', 'superset', 'drop_set')",
            name="ck_training_program_template_slots_method_values",
        ),
        sa.CheckConstraint(
            "rep_min BETWEEN 1 AND rep_max", name="ck_training_program_template_slots_reps"
        ),
        sa.CheckConstraint(
            "rest_seconds BETWEEN 0 AND 600", name="ck_training_program_template_slots_rest"
        ),
        sa.CheckConstraint("sets BETWEEN 1 AND 10", name="ck_training_program_template_slots_sets"),
        sa.CheckConstraint("slot_order >= 1", name="ck_training_program_template_slots_slot_order"),
        sa.CheckConstraint(
            "target_rir BETWEEN 0 AND 6", name="ck_training_program_template_slots_rir"
        ),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["template_day_id"], ["training_program_template_days.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "template_day_id", "slot_order", name="uq_training_program_template_slots_day_order"
        ),
    )
    op.create_index(
        "ix_training_program_template_slots_exercise_id",
        "training_program_template_slots",
        ["exercise_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_training_program_template_slots_exercise_id",
        table_name="training_program_template_slots",
    )
    op.drop_table("training_program_template_slots")
    op.drop_table("training_program_template_days")
    op.drop_index(
        "ix_training_program_templates_days_per_week",
        table_name="training_program_templates",
    )
    op.drop_table("training_program_templates")
