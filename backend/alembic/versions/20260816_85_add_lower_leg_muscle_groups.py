"""add abductors and legs exercise muscle groups"""

from collections.abc import Sequence

from alembic import op
from app.exercises.models import muscle_focus_compatibility_sql

revision: str = "20260816_85"
down_revision: str | Sequence[str] | None = "20260816_84"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MUSCLE_GROUPS = (
    "chest",
    "back",
    "shoulders",
    "biceps",
    "triceps",
    "traps",
    "forearms",
    "neck",
    "glutes",
    "quadriceps",
    "hamstrings",
    "adductors",
    "abductors",
    "legs",
    "calves",
    "abs",
    "obliques",
    "lower_back",
)
PREVIOUS_MUSCLE_GROUPS = tuple(
    value for value in MUSCLE_GROUPS if value not in {"abductors", "legs"}
)

_PRIMARY_CONSTRAINT = "ck_exercises_primary_muscle_values"
_SECONDARY_CONSTRAINT = "ck_exercise_secondary_muscles_muscle_values"
_COMPATIBILITY_CONSTRAINT = "ck_exercises_primary_muscle_focus_compatible"


def _quoted_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _create_constraints(values: tuple[str, ...]) -> None:
    quoted_values = _quoted_values(values)
    op.create_check_constraint(
        _PRIMARY_CONSTRAINT,
        "exercises",
        f"primary_muscle IN ({quoted_values})",
    )
    op.create_check_constraint(
        _SECONDARY_CONSTRAINT,
        "exercise_secondary_muscles",
        f"muscle IN ({quoted_values})",
    )
    op.create_check_constraint(
        _COMPATIBILITY_CONSTRAINT,
        "exercises",
        muscle_focus_compatibility_sql(),
    )


def upgrade() -> None:
    op.drop_constraint(_PRIMARY_CONSTRAINT, "exercises", type_="check")
    op.drop_constraint(_SECONDARY_CONSTRAINT, "exercise_secondary_muscles", type_="check")
    op.drop_constraint(_COMPATIBILITY_CONSTRAINT, "exercises", type_="check")
    _create_constraints(MUSCLE_GROUPS)


def downgrade() -> None:
    op.drop_constraint(_PRIMARY_CONSTRAINT, "exercises", type_="check")
    op.drop_constraint(_SECONDARY_CONSTRAINT, "exercise_secondary_muscles", type_="check")
    op.drop_constraint(_COMPATIBILITY_CONSTRAINT, "exercises", type_="check")
    _create_constraints(PREVIOUS_MUSCLE_GROUPS)
