"""add explicit repetition and duration prescriptions"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_103"
down_revision: str | Sequence[str] | None = "20260821_102"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRESCRIPTION_MODES = ("reps", "duration")
CANONICAL_DURATION_EXERCISES = {
    ("free-exercise-db", "0464"): (20, 40),
    ("free-exercise-db", "0705"): (20, 40),
    ("fitsho_training_template", "side-plank"): (20, 40),
}


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.add_column(
        "exercises",
        sa.Column(
            "prescription_mode",
            sa.String(length=16),
            server_default="reps",
            nullable=False,
        ),
    )
    op.add_column("exercises", sa.Column("duration_min_seconds", sa.SmallInteger()))
    op.add_column("exercises", sa.Column("duration_max_seconds", sa.SmallInteger()))
    op.create_check_constraint(
        "ck_exercises_prescription_mode_values",
        "exercises",
        f"prescription_mode IN ({_quoted(PRESCRIPTION_MODES)})",
    )
    op.create_check_constraint(
        "ck_exercises_prescription_contract",
        "exercises",
        "(prescription_mode = 'reps' AND duration_min_seconds IS NULL "
        "AND duration_max_seconds IS NULL) OR "
        "(prescription_mode = 'duration' "
        "AND duration_min_seconds BETWEEN 1 AND 3600 "
        "AND duration_max_seconds BETWEEN 1 AND 3600 "
        "AND duration_min_seconds <= duration_max_seconds)",
    )
    for (source, source_id), (duration_min, duration_max) in CANONICAL_DURATION_EXERCISES.items():
        op.execute(
            sa.text(
                "UPDATE exercises "
                "SET prescription_mode = 'duration', "
                "duration_min_seconds = :duration_min, "
                "duration_max_seconds = :duration_max "
                "WHERE source = :source AND source_id = :source_id"
            ).bindparams(
                source=source,
                source_id=source_id,
                duration_min=duration_min,
                duration_max=duration_max,
            )
        )

    op.add_column(
        "workout_plan_exercises",
        sa.Column(
            "prescription_mode",
            sa.String(length=16),
            server_default="reps",
            nullable=False,
        ),
    )
    op.add_column(
        "workout_plan_exercises",
        sa.Column("duration_min_seconds", sa.SmallInteger()),
    )
    op.add_column(
        "workout_plan_exercises",
        sa.Column("duration_max_seconds", sa.SmallInteger()),
    )
    op.alter_column("workout_plan_exercises", "reps_min", nullable=True)
    op.alter_column("workout_plan_exercises", "reps_max", nullable=True)
    op.alter_column("workout_plan_exercises", "rir", nullable=True)
    op.execute(
        sa.text(
            "UPDATE workout_plan_exercises AS plan_item "
            "SET prescription_mode = exercise.prescription_mode, "
            "duration_min_seconds = exercise.duration_min_seconds, "
            "duration_max_seconds = exercise.duration_max_seconds, "
            "reps_min = NULL, reps_max = NULL, rir = NULL "
            "FROM exercises AS exercise "
            "WHERE plan_item.exercise_id = exercise.id "
            "AND exercise.prescription_mode = 'duration'"
        )
    )
    op.create_check_constraint(
        "ck_workout_plan_exercises_prescription_mode_values",
        "workout_plan_exercises",
        f"prescription_mode IN ({_quoted(PRESCRIPTION_MODES)})",
    )
    op.create_check_constraint(
        "ck_workout_plan_exercises_prescription_contract",
        "workout_plan_exercises",
        "(prescription_mode = 'reps' "
        "AND reps_min BETWEEN 1 AND 100 "
        "AND reps_max BETWEEN 1 AND 100 "
        "AND reps_min <= reps_max "
        "AND duration_min_seconds IS NULL "
        "AND duration_max_seconds IS NULL "
        "AND rir BETWEEN 0 AND 5) OR "
        "(prescription_mode = 'duration' "
        "AND duration_min_seconds BETWEEN 1 AND 3600 "
        "AND duration_max_seconds BETWEEN 1 AND 3600 "
        "AND duration_min_seconds <= duration_max_seconds "
        "AND reps_min IS NULL "
        "AND reps_max IS NULL "
        "AND rir IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_workout_plan_exercises_prescription_contract",
        "workout_plan_exercises",
        type_="check",
    )
    op.drop_constraint(
        "ck_workout_plan_exercises_prescription_mode_values",
        "workout_plan_exercises",
        type_="check",
    )
    op.alter_column("workout_plan_exercises", "reps_min", nullable=False)
    op.alter_column("workout_plan_exercises", "reps_max", nullable=False)
    op.alter_column("workout_plan_exercises", "rir", nullable=False)
    op.drop_column("workout_plan_exercises", "duration_max_seconds")
    op.drop_column("workout_plan_exercises", "duration_min_seconds")
    op.drop_column("workout_plan_exercises", "prescription_mode")

    op.drop_constraint("ck_exercises_prescription_contract", "exercises", type_="check")
    op.drop_constraint("ck_exercises_prescription_mode_values", "exercises", type_="check")
    op.drop_column("exercises", "duration_max_seconds")
    op.drop_column("exercises", "duration_min_seconds")
    op.drop_column("exercises", "prescription_mode")
