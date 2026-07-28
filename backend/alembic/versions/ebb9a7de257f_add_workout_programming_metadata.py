"""add_workout_programming_metadata

Revision ID: ebb9a7de257f
Revises: 20260727_04
Create Date: 2026-07-28 15:17:15.544868

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "ebb9a7de257f"
down_revision = "20260727_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MOVEMENT_PATTERNS = (
    "horizontal_push",
    "vertical_push",
    "horizontal_pull",
    "vertical_pull",
    "squat",
    "hip_hinge",
    "lunge",
    "knee_extension",
    "knee_flexion",
    "hip_extension",
    "hip_abduction",
    "hip_adduction",
    "calf_raise",
    "elbow_flexion",
    "elbow_extension",
    "shoulder_abduction",
    "shoulder_external_rotation",
    "shrug",
    "spinal_flexion",
    "core_anti_extension",
    "core_anti_rotation",
    "core_anti_lateral_flexion",
    "other",
)
EXERCISE_TYPES = ("compound", "isolation", "core", "mobility", "other")
EXERCISE_CAUTION_TAGS = (
    "lower_back_loading",
    "spinal_flexion",
    "deep_knee_flexion",
    "overhead_position",
    "shoulder_internal_rotation",
    "shoulder_external_rotation",
    "wrist_loading",
    "neck_loading",
    "balance_demand",
    "other",
)


def quoted_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "exercises",
        sa.Column("movement_pattern", sa.String(length=50), server_default="other", nullable=False),
    )
    op.add_column(
        "exercises",
        sa.Column("exercise_type", sa.String(length=20), server_default="other", nullable=False),
    )
    op.add_column(
        "exercises",
        sa.Column("is_programmable", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_index("ix_exercises_is_programmable", "exercises", ["is_programmable"])
    op.create_check_constraint(
        "ck_exercises_movement_pattern_values",
        "exercises",
        f"movement_pattern IN ({quoted_values(MOVEMENT_PATTERNS)})",
    )
    op.create_check_constraint(
        "ck_exercises_exercise_type_values",
        "exercises",
        f"exercise_type IN ({quoted_values(EXERCISE_TYPES)})",
    )
    op.create_table(
        "exercise_caution_tags",
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("caution_tag", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("exercise_id", "caution_tag"),
        sa.CheckConstraint(
            f"caution_tag IN ({quoted_values(EXERCISE_CAUTION_TAGS)})",
            name="ck_exercise_caution_tags_caution_tag_values",
        ),
    )
    op.create_index(
        "ix_exercise_caution_tags_caution_tag", "exercise_caution_tags", ["caution_tag"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_exercise_caution_tags_caution_tag", table_name="exercise_caution_tags")
    op.drop_table("exercise_caution_tags")
    op.drop_index("ix_exercises_is_programmable", table_name="exercises")
    op.drop_constraint("ck_exercises_exercise_type_values", "exercises", type_="check")
    op.drop_constraint("ck_exercises_movement_pattern_values", "exercises", type_="check")
    op.drop_column("exercises", "is_programmable")
    op.drop_column("exercises", "exercise_type")
    op.drop_column("exercises", "movement_pattern")
