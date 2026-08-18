"""link body progress snapshots to workout cycles"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260818_94"
down_revision: str | Sequence[str] | None = "20260818_93"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "body_measurements",
        sa.Column("cycle_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_body_measurements_cycle_id",
        "body_measurements",
        ["cycle_id"],
    )
    op.create_foreign_key(
        "fk_body_measurements_cycle_id_workout_cycles",
        "body_measurements",
        "workout_cycles",
        ["cycle_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "body_photo_sessions",
        sa.Column("cycle_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_body_photo_sessions_cycle_id",
        "body_photo_sessions",
        ["cycle_id"],
    )
    op.create_foreign_key(
        "fk_body_photo_sessions_cycle_id_workout_cycles",
        "body_photo_sessions",
        "workout_cycles",
        ["cycle_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "body_analyses",
        sa.Column("cycle_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_body_analyses_cycle_id",
        "body_analyses",
        ["cycle_id"],
    )
    op.create_foreign_key(
        "fk_body_analyses_cycle_id_workout_cycles",
        "body_analyses",
        "workout_cycles",
        ["cycle_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_body_analyses_cycle_id_workout_cycles",
        "body_analyses",
        type_="foreignkey",
    )
    op.drop_index("ix_body_analyses_cycle_id", table_name="body_analyses")
    op.drop_column("body_analyses", "cycle_id")

    op.drop_constraint(
        "fk_body_photo_sessions_cycle_id_workout_cycles",
        "body_photo_sessions",
        type_="foreignkey",
    )
    op.drop_index("ix_body_photo_sessions_cycle_id", table_name="body_photo_sessions")
    op.drop_column("body_photo_sessions", "cycle_id")

    op.drop_constraint(
        "fk_body_measurements_cycle_id_workout_cycles",
        "body_measurements",
        type_="foreignkey",
    )
    op.drop_index("ix_body_measurements_cycle_id", table_name="body_measurements")
    op.drop_column("body_measurements", "cycle_id")
