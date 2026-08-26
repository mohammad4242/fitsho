"""Add persistent ownership state and upgrade the canonical template catalog.

Revision ID: 20260826_110
Revises: 20260825_109
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.orm import Session

from alembic import op
from app.training_templates.seed_data import SOURCE_NAME, SOURCE_URL
from app.training_templates.service import upgrade_training_program_template_catalog

revision: str = "20260826_110"
down_revision: str | Sequence[str] | None = "20260825_109"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "training_template_catalog_state",
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("catalog_revision", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )

    bind = op.get_bind()
    exercises = sa.table(
        "exercises",
        sa.column("source", sa.String()),
        sa.column("is_programmable", sa.Boolean()),
    )
    bind.execute(
        sa.update(exercises)
        .where(exercises.c.source == "fitsho_training_template")
        .values(is_programmable=False)
    )
    exercise_metadata = sa.table(
        "exercises",
        sa.column("slug", sa.String()),
        sa.column("movement_pattern", sa.String()),
    )
    bind.execute(
        sa.update(exercise_metadata)
        .where(exercise_metadata.c.slug == "fedb-2611-lever-horizontal-leg-press")
        .values(movement_pattern="squat")
    )
    bind.execute(
        sa.update(exercise_metadata)
        .where(exercise_metadata.c.slug == "fedb-1269-cable-standing-fly")
        .values(movement_pattern="horizontal_push")
    )
    templates = sa.table(
        "training_program_templates",
        sa.column("id", sa.Uuid()),
        sa.column("source_name", sa.String()),
        sa.column("source_url", sa.String()),
    )
    has_installed_catalog = bind.scalar(
        sa.select(sa.func.count())
        .select_from(templates)
        .where(
            templates.c.source_name == SOURCE_NAME,
            templates.c.source_url == SOURCE_URL,
        )
    )
    if has_installed_catalog:
        session = Session(bind=bind, join_transaction_mode="create_savepoint")
        try:
            upgrade_training_program_template_catalog(session)
        finally:
            session.close()


def downgrade() -> None:
    op.drop_table("training_template_catalog_state")
