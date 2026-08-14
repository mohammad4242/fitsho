"""add reviewed exercise muscle focus taxonomy"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.exercises.enums import MuscleFocus
from app.exercises.focus_manifest import FOCUS_MANIFEST
from app.exercises.models import muscle_focus_compatibility_sql

revision: str = "20260814_78"
down_revision: str | Sequence[str] | None = "20260814_77"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VALUE_CONSTRAINT = "ck_exercises_muscle_focus_values"
_COMPATIBILITY_CONSTRAINT = "ck_exercises_primary_muscle_focus_compatible"
_INDEX = "ix_exercises_primary_muscle_muscle_focus"


def _quoted_focus_values() -> str:
    return ", ".join(f"'{focus.value}'" for focus in MuscleFocus)


def upgrade() -> None:
    op.add_column(
        "exercises",
        sa.Column("muscle_focus", sa.String(length=40), nullable=True),
    )
    connection = op.get_bind()
    for entry in FOCUS_MANIFEST.values():
        values = {
            "primary_muscle": (
                entry.primary_muscle.value if entry.primary_muscle is not None else None
            ),
            "muscle_focus": entry.muscle_focus.value if entry.muscle_focus is not None else None,
        }
        if entry.key.startswith("slug:"):
            connection.execute(
                sa.text(
                    "UPDATE exercises SET primary_muscle = :primary_muscle, "
                    "muscle_focus = :muscle_focus WHERE slug = :slug"
                ),
                {**values, "slug": entry.slug},
            )
            continue
        source, source_id = entry.key.split(":", 1)
        connection.execute(
            sa.text(
                "UPDATE exercises SET primary_muscle = :primary_muscle, "
                "muscle_focus = :muscle_focus "
                "WHERE source = :source AND source_id = :source_id"
            ),
            {**values, "source": source, "source_id": source_id},
        )

    unresolved = connection.execute(
        sa.text(
            "SELECT slug FROM exercises "
            "WHERE primary_muscle IS NOT NULL AND muscle_focus IS NULL "
            "ORDER BY slug"
        )
    ).scalars()
    unresolved_slugs = list(unresolved)
    if unresolved_slugs:
        raise RuntimeError(
            "Exercise muscle-focus migration has unresolved records: "
            + ", ".join(unresolved_slugs)
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
    op.create_index(
        _INDEX,
        "exercises",
        ["primary_muscle", "muscle_focus"],
    )


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="exercises")
    op.drop_constraint(_COMPATIBILITY_CONSTRAINT, "exercises", type_="check")
    op.drop_constraint(_VALUE_CONSTRAINT, "exercises", type_="check")
    op.drop_column("exercises", "muscle_focus")
