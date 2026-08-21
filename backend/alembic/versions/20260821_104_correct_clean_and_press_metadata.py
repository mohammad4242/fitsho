"""correct canonical clean-and-press programming metadata"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260821_104"
down_revision: str | Sequence[str] | None = "20260821_103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_WHERE = "source = 'free-exercise-db' AND source_id = '0028'"


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE exercises "
            "SET primary_muscle = 'shoulders', muscle_focus = 'front_delt', "
            "movement_pattern = 'vertical_push', exercise_type = 'compound', "
            "skill_demand = 'high', stability_demand = 'high', fatigue_cost = 4 "
            f"WHERE {_WHERE}"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM exercise_secondary_muscles WHERE exercise_id IN "
            "(SELECT id FROM exercises "
            f"WHERE {_WHERE})"
        )
    )
    for muscle in ("quadriceps", "glutes", "triceps", "traps"):
        op.execute(
            sa.text(
                "INSERT INTO exercise_secondary_muscles (exercise_id, muscle) "
                "SELECT id, :muscle FROM exercises "
                f"WHERE {_WHERE}"
            ).bindparams(muscle=muscle)
        )
    op.execute(
        sa.text(
            "INSERT INTO exercise_label_items (exercise_id, label) "
            "SELECT id, 'full_body' FROM exercises "
            f"WHERE {_WHERE} "
            "AND NOT EXISTS (SELECT 1 FROM exercise_label_items "
            "WHERE exercise_id = exercises.id AND label = 'full_body')"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO exercise_caution_tags (exercise_id, caution_tag) "
            "SELECT id, 'overhead_position' FROM exercises "
            f"WHERE {_WHERE} "
            "AND NOT EXISTS (SELECT 1 FROM exercise_caution_tags "
            "WHERE exercise_id = exercises.id AND caution_tag = 'overhead_position')"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM exercise_caution_tags WHERE caution_tag = 'overhead_position' "
            "AND exercise_id IN (SELECT id FROM exercises "
            f"WHERE {_WHERE})"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM exercise_label_items WHERE label = 'full_body' "
            "AND exercise_id IN (SELECT id FROM exercises "
            f"WHERE {_WHERE})"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM exercise_secondary_muscles "
            "WHERE muscle IN ('quadriceps', 'glutes', 'triceps', 'traps') "
            "AND exercise_id IN (SELECT id FROM exercises "
            f"WHERE {_WHERE})"
        )
    )
    op.execute(
        sa.text(
            "UPDATE exercises "
            "SET primary_muscle = 'quadriceps', muscle_focus = NULL, "
            "movement_pattern = 'knee_extension', exercise_type = 'isolation', "
            "skill_demand = NULL, stability_demand = NULL, fatigue_cost = NULL "
            f"WHERE {_WHERE}"
        )
    )
