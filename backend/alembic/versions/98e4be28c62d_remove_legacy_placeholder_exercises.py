"""remove legacy placeholder exercises

Revision ID: 98e4be28c62d
Revises: 67c29dbb63ca
Create Date: 2026-08-28 00:59:46.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "98e4be28c62d"
down_revision: str | Sequence[str] | None = "67c29dbb63ca"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PLACEHOLDER_SLUGS = [
    "barbell-shrug",
    "bulgarian-split-squat",
    "cable-curl",
    "cable-lateral-raise",
    "cable-pullover",
    "chest-supported-row",
    "dead-bug",
    "dumbbell-shrug",
    "face-pull",
    "lying-leg-curl",
    "machine-chest-press",
    "overhead-dumbbell-extension",
    "pallof-press",
    "pec-deck-fly",
    "preacher-curl",
    "rear-delt-fly",
    "rope-overhead-extension",
    "seated-calf-raise",
    "side-plank",
    "single-arm-cable-row",
    "skull-crusher",
]


def upgrade() -> None:
    conn = op.get_bind()
    params = {"slugs": PLACEHOLDER_SLUGS}

    # 1. Delete dependent associations and child tables
    conn.execute(
        sa.text(
            """
            DELETE FROM exercise_equipment
            WHERE exercise_id IN (SELECT id FROM exercises WHERE slug = ANY(:slugs));
            """
        ),
        params,
    )

    conn.execute(
        sa.text(
            """
            DELETE FROM exercise_secondary_muscles
            WHERE exercise_id IN (SELECT id FROM exercises WHERE slug = ANY(:slugs));
            """
        ),
        params,
    )

    conn.execute(
        sa.text(
            """
            DELETE FROM exercise_caution_tags
            WHERE exercise_id IN (SELECT id FROM exercises WHERE slug = ANY(:slugs));
            """
        ),
        params,
    )

    conn.execute(
        sa.text(
            """
            DELETE FROM exercise_media_assets
            WHERE exercise_id IN (SELECT id FROM exercises WHERE slug = ANY(:slugs));
            """
        ),
        params,
    )

    conn.execute(
        sa.text(
            """
            DELETE FROM exercise_label_items
            WHERE exercise_id IN (SELECT id FROM exercises WHERE slug = ANY(:slugs));
            """
        ),
        params,
    )

    conn.execute(
        sa.text(
            """
            DELETE FROM exercise_alternatives
            WHERE exercise_id IN (SELECT id FROM exercises WHERE slug = ANY(:slugs))
               OR alternative_exercise_id IN (SELECT id FROM exercises WHERE slug = ANY(:slugs));
            """
        ),
        params,
    )

    conn.execute(
        sa.text(
            """
            DELETE FROM workout_exercise_replacements
            WHERE original_exercise_id IN (SELECT id FROM exercises WHERE slug = ANY(:slugs))
               OR replacement_exercise_id IN (SELECT id FROM exercises WHERE slug = ANY(:slugs));
            """
        ),
        params,
    )

    conn.execute(
        sa.text(
            """
            DELETE FROM workout_exercise_safety_signals
            WHERE original_exercise_id IN (SELECT id FROM exercises WHERE slug = ANY(:slugs))
               OR replacement_exercise_id IN (SELECT id FROM exercises WHERE slug = ANY(:slugs));
            """
        ),
        params,
    )

    conn.execute(
        sa.text(
            """
            DELETE FROM workout_exercise_preferences
            WHERE exercise_id IN (SELECT id FROM exercises WHERE slug = ANY(:slugs));
            """
        ),
        params,
    )

    conn.execute(
        sa.text(
            """
            DELETE FROM workout_cycle_exercise_feedback
            WHERE exercise_id IN (SELECT id FROM exercises WHERE slug = ANY(:slugs));
            """
        ),
        params,
    )

    conn.execute(
        sa.text(
            """
            DELETE FROM training_program_template_slots
            WHERE exercise_id IN (SELECT id FROM exercises WHERE slug = ANY(:slugs))
               OR superset_exercise_id IN (SELECT id FROM exercises WHERE slug = ANY(:slugs));
            """
        ),
        params,
    )

    conn.execute(
        sa.text(
            """
            DELETE FROM workout_plan_exercises
            WHERE exercise_id IN (SELECT id FROM exercises WHERE slug = ANY(:slugs));
            """
        ),
        params,
    )

    # 2. Delete the placeholder exercises
    conn.execute(
        sa.text(
            """
            DELETE FROM exercises
            WHERE slug = ANY(:slugs);
            """
        ),
        params,
    )


def downgrade() -> None:
    pass
