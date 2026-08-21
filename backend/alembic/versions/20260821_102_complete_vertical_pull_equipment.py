from collections.abc import Sequence

from alembic import op

revision: str = "20260821_102"
down_revision: str | Sequence[str] | None = "20260820_101"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TARGET = """
    source = 'free-exercise-db'
    AND movement_pattern = 'vertical_pull'
    AND (
        EXISTS (
            SELECT 1
            FROM exercise_equipment existing_bodyweight
            WHERE existing_bodyweight.exercise_id = exercises.id
              AND existing_bodyweight.equipment = 'bodyweight'
        )
        OR lower(name_en) LIKE '%pull-up%'
        OR lower(name_en) LIKE '%pull up%'
        OR lower(name_en) LIKE '%chin-up%'
        OR lower(name_en) LIKE '%chin up%'
    )
"""


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO exercise_equipment (exercise_id, equipment)
        SELECT exercises.id, 'pull_up_bar'
        FROM exercises
        WHERE {_TARGET}
        ON CONFLICT (exercise_id, equipment) DO NOTHING
        """
    )
    op.execute(
        f"""
        INSERT INTO exercise_equipment (exercise_id, equipment)
        SELECT exercises.id, 'bench'
        FROM exercises
        WHERE {_TARGET}
          AND lower(name_en) LIKE '%bench%'
          AND lower(name_en) LIKE '%pull%'
        ON CONFLICT (exercise_id, equipment) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM exercise_equipment
        WHERE equipment IN ('pull_up_bar', 'bench')
          AND exercise_id IN (
              SELECT exercises.id
              FROM exercises
              WHERE {_TARGET}
          )
        """
    )
