"""Consolidate training templates around shared supported levels.

Revision ID: 20260825_108
Revises: 20260824_107
Create Date: 2026-08-25
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260825_108"
down_revision: str | Sequence[str] | None = "20260824_107"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SOURCE_NAME = "Fitsho canonical training template catalog"
_SOURCE_URL = "https://fitsho.local/training-template-catalog"
_LEVELS = ("first_month", "beginner", "intermediate", "advanced")
_LEVEL_SUFFIXES = {
    "first_month": "first-month",
    "beginner": "beginner",
    "intermediate": "intermediate",
    "advanced": "advanced",
}
_CANONICAL_SLUGS = (
    "t01-2-day-full-body-ab",
    "t02-3-day-upper-lower-full",
    "t03-3-day-upper-lower-upper",
    "t04-3-day-lower-upper-lower",
    "t05-4-day-upper-lower-2x",
    "t06-4-day-3-upper-1-lower",
    "t07-4-day-3-lower-1-upper",
    "t08-4-day-push-pull-quads-posterior",
    "t09-5-day-ppl-upper-lower",
    "t10-5-day-classic-body-part",
    "t11-5-day-ppl-upper-lower-priority",
    "t12-5-day-chest-specialization",
    "t13-5-day-back-specialization",
    "t14-5-day-leg-specialization",
    "t15-6-day-ppl-2x",
    "t16-6-day-advanced-body-part",
    "t17-6-day-balanced-specialization",
)


def _templates_table() -> sa.TableClause:
    return sa.table(
        "training_program_templates",
        sa.column("id", sa.Uuid()),
        sa.column("slug", sa.String()),
        sa.column("training_level", sa.String()),
        sa.column("supported_levels", sa.JSON()),
        sa.column("source_name", sa.String()),
        sa.column("source_url", sa.String()),
    )


def upgrade() -> None:
    op.add_column(
        "training_program_templates",
        sa.Column("supported_levels", sa.JSON(), nullable=True),
    )

    bind = op.get_bind()
    templates = _templates_table()
    bind.execute(
        templates.update().values(
            supported_levels=sa.func.json_build_array(templates.c.training_level)
        )
    )

    for canonical_slug in _CANONICAL_SLUGS:
        group_slugs = [
            canonical_slug,
            *(f"{canonical_slug}-{_LEVEL_SUFFIXES[level]}" for level in _LEVELS),
        ]
        rows = list(
            bind.execute(
                sa.select(
                    templates.c.id,
                    templates.c.slug,
                    templates.c.training_level,
                ).where(
                    templates.c.source_name == _SOURCE_NAME,
                    templates.c.source_url == _SOURCE_URL,
                    templates.c.slug.in_(group_slugs),
                )
            ).mappings()
        )
        if not rows:
            continue

        keeper = next(
            (row for row in rows if row["slug"] == canonical_slug),
            min(rows, key=lambda row: str(row["id"])),
        )
        supported_levels = [
            level for level in _LEVELS if any(row["training_level"] == level for row in rows)
        ]
        duplicate_ids = [row["id"] for row in rows if row["id"] != keeper["id"]]
        if duplicate_ids:
            bind.execute(templates.delete().where(templates.c.id.in_(duplicate_ids)))
        bind.execute(
            templates.update()
            .where(templates.c.id == keeper["id"])
            .values(slug=canonical_slug, supported_levels=supported_levels)
        )

    op.alter_column(
        "training_program_templates",
        "supported_levels",
        existing_type=sa.JSON(),
        nullable=False,
    )
    op.create_check_constraint(
        "ck_training_program_templates_supported_levels",
        "training_program_templates",
        "json_typeof(supported_levels) = 'array' "
        "AND json_array_length(supported_levels) BETWEEN 1 AND 4 "
        "AND supported_levels::jsonb <@ "
        '\'["first_month", "beginner", "intermediate", "advanced"]\'::jsonb',
    )
    op.drop_constraint(
        "ck_training_program_templates_training_level_values",
        "training_program_templates",
        type_="check",
    )
    op.drop_column("training_program_templates", "training_level")


def downgrade() -> None:
    op.add_column(
        "training_program_templates",
        sa.Column("training_level", sa.String(length=12), nullable=True),
    )
    op.execute("UPDATE training_program_templates SET training_level = supported_levels ->> 0")
    op.alter_column(
        "training_program_templates",
        "training_level",
        existing_type=sa.String(length=12),
        nullable=False,
    )
    op.create_check_constraint(
        "ck_training_program_templates_training_level_values",
        "training_program_templates",
        "training_level IN ('first_month', 'beginner', 'intermediate', 'advanced')",
    )
    op.drop_constraint(
        "ck_training_program_templates_supported_levels",
        "training_program_templates",
        type_="check",
    )
    op.drop_column("training_program_templates", "supported_levels")
