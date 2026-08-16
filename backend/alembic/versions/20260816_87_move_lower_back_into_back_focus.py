"""move lower-back exercises into the back focus taxonomy"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.exercises.enums import MuscleFocus
from app.exercises.models import muscle_focus_compatibility_sql

revision: str = "20260816_87"
down_revision: str | Sequence[str] | None = "20260816_86"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COMPATIBILITY_CONSTRAINT = "ck_exercises_primary_muscle_focus_compatible"
_VALUE_CONSTRAINT = "ck_exercises_muscle_focus_values"
_OLD_PRIMARY = "lower_back"
_NEW_PRIMARY = "back"
_NEW_FOCUS = "lower_back"
_OLD_LUMBAR_FOCUS = "lumbar_erectors"
_OLD_THORACIC_FOCUS = "thoracic_mobility"

_KNOWN_THORACIC_SOURCE_IDS = (
    "drv-stretching-kneeling-back-rotation-stretch-kneeling-back-rotation-stretch",
)


def _quoted_focus_values() -> str:
    return ", ".join(f"'{focus.value}'" for focus in MuscleFocus)


def upgrade() -> None:
    op.drop_constraint(_VALUE_CONSTRAINT, "exercises", type_="check")
    op.drop_constraint(_COMPATIBILITY_CONSTRAINT, "exercises", type_="check")
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE exercises SET primary_muscle = :new_primary, muscle_focus = :new_focus "
            "WHERE primary_muscle = :old_primary"
        ),
        {
            "new_primary": _NEW_PRIMARY,
            "new_focus": _NEW_FOCUS,
            "old_primary": _OLD_PRIMARY,
        },
    )
    op.create_check_constraint(
        _VALUE_CONSTRAINT,
        "exercises",
        f"muscle_focus IS NULL OR muscle_focus IN ({_quoted_focus_values()})",
    )
    op.create_check_constraint(
        _COMPATIBILITY_CONSTRAINT,
        "exercises",
        muscle_focus_compatibility_sql(),
    )


def downgrade() -> None:
    op.drop_constraint(_VALUE_CONSTRAINT, "exercises", type_="check")
    op.drop_constraint(_COMPATIBILITY_CONSTRAINT, "exercises", type_="check")
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE exercises SET primary_muscle = :old_primary, muscle_focus = :old_focus "
            "WHERE primary_muscle = :new_primary AND muscle_focus = :new_focus"
        ),
        {
            "old_primary": _OLD_PRIMARY,
            "old_focus": _OLD_LUMBAR_FOCUS,
            "new_primary": _NEW_PRIMARY,
            "new_focus": _NEW_FOCUS,
        },
    )
    for source_id in _KNOWN_THORACIC_SOURCE_IDS:
        connection.execute(
            sa.text(
                "UPDATE exercises SET muscle_focus = :old_focus "
                "WHERE source = 'free-exercise-db' AND source_id = :source_id "
                "AND primary_muscle = :old_primary"
            ),
            {
                "old_focus": _OLD_THORACIC_FOCUS,
                "source_id": source_id,
                "old_primary": _OLD_PRIMARY,
            },
        )
    op.create_check_constraint(
        _VALUE_CONSTRAINT,
        "exercises",
        f"muscle_focus IS NULL OR muscle_focus IN ({_quoted_focus_values()})",
    )
    op.create_check_constraint(
        _COMPATIBILITY_CONSTRAINT,
        "exercises",
        muscle_focus_compatibility_sql(),
    )
