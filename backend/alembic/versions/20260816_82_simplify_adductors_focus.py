"""simplify adductors focus taxonomy"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from app.exercises.enums import MuscleFocus, MuscleGroup
from app.exercises.models import muscle_focus_compatibility_sql
from app.exercises.taxonomy import FOCUSES_BY_MUSCLE

revision: str = "20260816_82"
down_revision: str | Sequence[str] | None = "20260816_81"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COMPATIBILITY_CONSTRAINT = "ck_exercises_primary_muscle_focus_compatible"
_PREVIOUS_ADDUCTOR_FOCUSES = (
    MuscleFocus.HIP_ADDUCTION,
    MuscleFocus.ADDUCTOR_MOBILITY,
)
_PREVIOUS_MOBILITY_SLUGS = {
    "fedb-drv-stretching-adductor-stretch-standing-adductor-stretch",
    "fedb-drv-stretching-all-fours-squad-stretch-all-fours-groin-stretch",
    "fedb-drv-stretching-boat-stretch-seated-boat-stretch",
    "fedb-drv-stretching-plyo-side-lunge-stretch-plyometric-side-lunge-stretch",
}


def _previous_compatibility_sql() -> str:
    previous_focuses = {
        **FOCUSES_BY_MUSCLE,
        MuscleGroup.ADDUCTORS: _PREVIOUS_ADDUCTOR_FOCUSES,
    }
    compatible_pairs = []
    for muscle, focuses in previous_focuses.items():
        if not focuses:
            continue
        focus_values = ", ".join(f"'{focus.value}'" for focus in focuses)
        compatible_pairs.append(
            f"(primary_muscle = '{muscle.value}' AND muscle_focus IN ({focus_values}))"
        )
    muscle_values = ", ".join(f"'{muscle.value}'" for muscle in MuscleGroup)
    focusless_muscle_values = ", ".join(
        f"'{muscle.value}'" for muscle, focuses in previous_focuses.items() if not focuses
    )
    focus_values = ", ".join(f"'{focus.value}'" for focus in MuscleFocus)
    return (
        "(primary_muscle IS NULL AND muscle_focus IS NULL) OR "
        f"(primary_muscle IN ({focusless_muscle_values}) AND muscle_focus IS NULL) OR "
        "(primary_muscle IS NOT NULL AND muscle_focus IS NOT NULL AND ("
        f"primary_muscle NOT IN ({muscle_values}) OR "
        f"muscle_focus NOT IN ({focus_values}) OR "
        f"{' OR '.join(compatible_pairs)}))"
    )


def upgrade() -> None:
    op.drop_constraint(_COMPATIBILITY_CONSTRAINT, "exercises", type_="check")
    op.execute(
        sa.text(
            "UPDATE exercises SET muscle_focus = NULL "
            "WHERE primary_muscle = 'adductors'"
        )
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
            "UPDATE exercises SET muscle_focus = 'hip_adduction' "
            "WHERE primary_muscle = 'adductors'"
        )
    )
    connection = op.get_bind()
    for slug in _PREVIOUS_MOBILITY_SLUGS:
        connection.execute(
            sa.text(
                "UPDATE exercises SET muscle_focus = 'adductor_mobility' "
                "WHERE slug = :slug AND primary_muscle = 'adductors'"
            ),
            {"slug": slug},
        )
    op.create_check_constraint(
        _COMPATIBILITY_CONSTRAINT,
        "exercises",
        _previous_compatibility_sql(),
    )
