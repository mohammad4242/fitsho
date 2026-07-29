"""add exercise labels and nullable anatomy

Revision ID: 20260730_08
Revises: 6b8f1d2c4e90
Create Date: 2026-07-30 23:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260730_08"
down_revision: str | Sequence[str] | None = "6b8f1d2c4e90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MUSCLE_GROUPS = (
    "chest", "back", "shoulders", "biceps", "triceps", "traps", "forearms", "neck",
    "glutes", "quadriceps", "hamstrings", "adductors", "calves", "abs", "obliques",
    "lower_back",
)
PREVIOUS_MUSCLE_GROUPS = tuple(
    value for value in MUSCLE_GROUPS if value not in {"forearms", "neck"}
)
EXERCISE_LABELS = ("full_body", "cardio")


def quoted_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.drop_constraint("ck_exercises_primary_muscle_values", "exercises", type_="check")
    op.drop_constraint(
        "ck_exercise_secondary_muscles_muscle_values",
        "exercise_secondary_muscles",
        type_="check",
    )
    op.alter_column("exercises", "body_region", existing_type=sa.String(length=10), nullable=True)
    op.alter_column(
        "exercises",
        "primary_muscle",
        existing_type=sa.String(length=14),
        nullable=True,
    )
    op.create_check_constraint(
        "ck_exercises_primary_muscle_values",
        "exercises",
        f"primary_muscle IN ({quoted_values(MUSCLE_GROUPS)})",
    )
    op.create_check_constraint(
        "ck_exercise_secondary_muscles_muscle_values",
        "exercise_secondary_muscles",
        f"muscle IN ({quoted_values(MUSCLE_GROUPS)})",
    )
    op.create_table(
        "exercise_label_items",
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=20), nullable=False),
        sa.CheckConstraint(
            f"label IN ({quoted_values(EXERCISE_LABELS)})",
            name="ck_exercise_label_items_label_values",
        ),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercises.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("exercise_id", "label"),
    )
    op.create_index("ix_exercise_label_items_label", "exercise_label_items", ["label"])


def downgrade() -> None:
    bind = op.get_bind()
    unresolved = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM exercises "
            "WHERE body_region IS NULL OR primary_muscle IS NULL "
            "OR primary_muscle IN ('forearms', 'neck')) "
            "OR EXISTS (SELECT 1 FROM exercise_secondary_muscles "
            "WHERE muscle IN ('forearms', 'neck'))"
        )
    ).scalar_one()
    if unresolved:
        raise RuntimeError("Cannot downgrade while taxonomy-only exercise values exist")
    op.drop_index("ix_exercise_label_items_label", table_name="exercise_label_items")
    op.drop_table("exercise_label_items")
    op.drop_constraint("ck_exercises_primary_muscle_values", "exercises", type_="check")
    op.drop_constraint(
        "ck_exercise_secondary_muscles_muscle_values",
        "exercise_secondary_muscles",
        type_="check",
    )
    op.alter_column(
        "exercises",
        "primary_muscle",
        existing_type=sa.String(length=14),
        nullable=False,
    )
    op.alter_column("exercises", "body_region", existing_type=sa.String(length=10), nullable=False)
    op.create_check_constraint(
        "ck_exercises_primary_muscle_values",
        "exercises",
        f"primary_muscle IN ({quoted_values(PREVIOUS_MUSCLE_GROUPS)})",
    )
    op.create_check_constraint(
        "ck_exercise_secondary_muscles_muscle_values",
        "exercise_secondary_muscles",
        f"muscle IN ({quoted_values(PREVIOUS_MUSCLE_GROUPS)})",
    )
