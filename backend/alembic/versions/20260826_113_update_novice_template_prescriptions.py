"""Update legacy novice template prescriptions without replacing admin edits.

Revision ID: 20260826_113
Revises: 20260826_112
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260826_113"
down_revision: str | Sequence[str] | None = "20260826_112"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CANONICAL_SOURCE_NAME = "Fitsho canonical training template catalog"
_CANONICAL_SOURCE_URL = "https://fitsho.local/training-template-catalog"
_NOVICE_LEVELS = ("first_month", "beginner")
_LEGACY_PRESCRIPTIONS = ((2, 10, 15), (2, 12, 15), (2, 12, 20))
_CURRENT_PRESCRIPTION = (3, 8, 12)


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE training_program_template_slots AS slots
            SET sets = :current_sets,
                rep_min = :current_rep_min,
                rep_max = :current_rep_max
            FROM training_program_template_days AS days
            JOIN training_program_templates AS templates
              ON templates.id = days.template_id
            WHERE slots.template_day_id = days.id
              AND templates.source_name = :source_name
              AND templates.source_url = :source_url
              AND templates.supported_levels::jsonb ?| CAST(:novice_levels AS text[])
              AND (slots.sets, slots.rep_min, slots.rep_max) IN (
                    (:legacy_sets_1, :legacy_rep_min_1, :legacy_rep_max_1),
                    (:legacy_sets_2, :legacy_rep_min_2, :legacy_rep_max_2),
                    (:legacy_sets_3, :legacy_rep_min_3, :legacy_rep_max_3)
              )
            """
        ),
        {
            "current_sets": _CURRENT_PRESCRIPTION[0],
            "current_rep_min": _CURRENT_PRESCRIPTION[1],
            "current_rep_max": _CURRENT_PRESCRIPTION[2],
            "source_name": _CANONICAL_SOURCE_NAME,
            "source_url": _CANONICAL_SOURCE_URL,
            "novice_levels": list(_NOVICE_LEVELS),
            "legacy_sets_1": _LEGACY_PRESCRIPTIONS[0][0],
            "legacy_rep_min_1": _LEGACY_PRESCRIPTIONS[0][1],
            "legacy_rep_max_1": _LEGACY_PRESCRIPTIONS[0][2],
            "legacy_sets_2": _LEGACY_PRESCRIPTIONS[1][0],
            "legacy_rep_min_2": _LEGACY_PRESCRIPTIONS[1][1],
            "legacy_rep_max_2": _LEGACY_PRESCRIPTIONS[1][2],
            "legacy_sets_3": _LEGACY_PRESCRIPTIONS[2][0],
            "legacy_rep_min_3": _LEGACY_PRESCRIPTIONS[2][1],
            "legacy_rep_max_3": _LEGACY_PRESCRIPTIONS[2][2],
        },
    )
    bind.execute(
        sa.text(
            """
            UPDATE training_template_catalog_state
            SET catalog_revision = :catalog_revision
            WHERE key = 'canonical'
            """
        ),
        {"catalog_revision": 7},
    )


def downgrade() -> None:
    # The migration intentionally does not reverse prescriptions because that could
    # overwrite an admin edit made after the upgrade.
    pass
