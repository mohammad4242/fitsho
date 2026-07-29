"""add exercise import metadata

Revision ID: f6e34c2a8b19
Revises: 9a0e535a9e11
Create Date: 2026-07-29 23:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6e34c2a8b19"
down_revision: str | Sequence[str] | None = "9a0e535a9e11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("exercises", sa.Column("source", sa.String(length=80), nullable=True))
    op.add_column("exercises", sa.Column("source_id", sa.String(length=160), nullable=True))
    op.add_column("exercises", sa.Column("aliases_en", sa.JSON(), nullable=True))
    op.add_column(
        "exercises", sa.Column("short_description_en", sa.String(length=1000), nullable=True)
    )
    op.add_column("exercises", sa.Column("steps_en", sa.JSON(), nullable=True))
    op.add_column("exercises", sa.Column("form_cues_en", sa.JSON(), nullable=True))
    op.add_column("exercises", sa.Column("common_mistakes_en", sa.JSON(), nullable=True))
    op.add_column("exercises", sa.Column("breathing_en", sa.String(length=1000), nullable=True))
    op.add_column("exercises", sa.Column("source_metadata_en", sa.JSON(), nullable=True))
    op.add_column(
        "exercises",
        sa.Column("needs_review", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_unique_constraint(
        "uq_exercises_source_source_id", "exercises", ["source", "source_id"]
    )
    op.drop_constraint("ck_exercises_safety_notes_en_items", "exercises", type_="check")
    op.drop_constraint("ck_exercises_safety_notes_fa_items", "exercises", type_="check")
    op.create_check_constraint(
        "ck_exercises_safety_notes_en_items",
        "exercises",
        "json_typeof(safety_notes_en) = 'array'",
    )
    op.create_check_constraint(
        "ck_exercises_safety_notes_fa_items",
        "exercises",
        "json_typeof(safety_notes_fa) = 'array'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_exercises_safety_notes_fa_items", "exercises", type_="check")
    op.drop_constraint("ck_exercises_safety_notes_en_items", "exercises", type_="check")
    op.create_check_constraint(
        "ck_exercises_safety_notes_en_items",
        "exercises",
        "json_typeof(safety_notes_en) = 'array' AND json_array_length(safety_notes_en) >= 1",
    )
    op.create_check_constraint(
        "ck_exercises_safety_notes_fa_items",
        "exercises",
        "json_typeof(safety_notes_fa) = 'array' AND json_array_length(safety_notes_fa) >= 1",
    )
    op.drop_constraint("uq_exercises_source_source_id", "exercises", type_="unique")
    op.drop_column("exercises", "needs_review")
    op.drop_column("exercises", "source_metadata_en")
    op.drop_column("exercises", "breathing_en")
    op.drop_column("exercises", "common_mistakes_en")
    op.drop_column("exercises", "form_cues_en")
    op.drop_column("exercises", "steps_en")
    op.drop_column("exercises", "short_description_en")
    op.drop_column("exercises", "aliases_en")
    op.drop_column("exercises", "source_id")
    op.drop_column("exercises", "source")
