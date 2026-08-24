"""simplify quadriceps focus taxonomy"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.exercises.enums import MuscleFocus, MuscleGroup
from app.exercises.models import muscle_focus_compatibility_sql
from app.exercises.taxonomy import FOCUSES_BY_MUSCLE

revision: str = "20260814_79"
down_revision: str | Sequence[str] | None = "20260814_78"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COMPATIBILITY_CONSTRAINT = "ck_exercises_primary_muscle_focus_compatible"
_PREVIOUS_QUADRICEPS_FOCUSES = (
    MuscleFocus.GENERAL_QUADRICEPS,
    MuscleFocus.RECTUS_FEMORIS,
    MuscleFocus.VASTI,
)
_PREVIOUS_FOCUS_BY_SLUG = {
    "fedb-0585-lever-leg-extension": MuscleFocus.VASTI,
    "fedb-0740-sled-45-degree-wide-leg-press": MuscleFocus.VASTI,
    "fedb-0748-smith-machine-leg-press": MuscleFocus.VASTI,
    "fedb-0851-weighted-sissy-squat": MuscleFocus.RECTUS_FEMORIS,
    "fedb-0980-band-seated-leg-extension": MuscleFocus.VASTI,
    "fedb-1564-hip-flexor-and-quadriceps-stretch": MuscleFocus.RECTUS_FEMORIS,
    "fedb-2611-lever-horizontal-leg-press": MuscleFocus.VASTI,
    "fedb-drv-close-feet-leg-press-close-feet-leg-press": MuscleFocus.VASTI,
    "fedb-drv-stretching-quadriceps-lying-stretch-lying-quadriceps-stretch": (
        MuscleFocus.RECTUS_FEMORIS
    ),
    "fedb-drv-stretching-quadriceps-stretch-standing-quadriceps-stretch": (
        MuscleFocus.RECTUS_FEMORIS
    ),
}


def _previous_compatibility_sql() -> str:
    previous_focuses = {
        **FOCUSES_BY_MUSCLE,
        MuscleGroup.QUADRICEPS: _PREVIOUS_QUADRICEPS_FOCUSES,
    }
    compatible_pairs = []
    for muscle, focuses in previous_focuses.items():
        focus_values = ", ".join(f"'{focus.value}'" for focus in focuses)
        compatible_pairs.append(
            f"(primary_muscle = '{muscle.value}' AND muscle_focus IN ({focus_values}))"
        )
    muscle_values = ", ".join(f"'{muscle.value}'" for muscle in MuscleGroup)
    focus_values = ", ".join(f"'{focus.value}'" for focus in MuscleFocus)
    return (
        "(primary_muscle IS NULL AND muscle_focus IS NULL) OR "
        "(primary_muscle IS NOT NULL AND muscle_focus IS NOT NULL AND ("
        f"primary_muscle NOT IN ({muscle_values}) OR "
        f"muscle_focus NOT IN ({focus_values}) OR "
        f"{' OR '.join(compatible_pairs)}))"
    )


def upgrade() -> None:
    op.drop_constraint(_COMPATIBILITY_CONSTRAINT, "exercises", type_="check")
    op.execute(
        sa.text("UPDATE exercises SET muscle_focus = NULL WHERE primary_muscle = 'quadriceps'")
    )
    op.create_check_constraint(
        _COMPATIBILITY_CONSTRAINT,
        "exercises",
        muscle_focus_compatibility_sql(),
    )


def downgrade() -> None:
    op.drop_constraint(_COMPATIBILITY_CONSTRAINT, "exercises", type_="check")
    op.execute(
        sa.text(
            "UPDATE exercises SET muscle_focus = 'general_quadriceps' "
            "WHERE primary_muscle = 'quadriceps'"
        )
    )
    connection = op.get_bind()
    for slug, focus in _PREVIOUS_FOCUS_BY_SLUG.items():
        connection.execute(
            sa.text(
                "UPDATE exercises SET muscle_focus = :muscle_focus "
                "WHERE slug = :slug AND primary_muscle = 'quadriceps'"
            ),
            {"slug": slug, "muscle_focus": focus.value},
        )
    op.create_check_constraint(
        _COMPATIBILITY_CONSTRAINT,
        "exercises",
        _previous_compatibility_sql(),
    )
