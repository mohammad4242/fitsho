"""add owner video media provenance"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260814_80"
down_revision: str | Sequence[str] | None = "20260814_79"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRESENTATION_CONSTRAINT = "ck_exercise_media_assets_presentation_values"
_SOURCE_CONSTRAINT = "uq_exercise_media_assets_source_source_id"


def upgrade() -> None:
    op.drop_constraint(
        _PRESENTATION_CONSTRAINT,
        "exercise_media_assets",
        type_="check",
    )
    op.alter_column(
        "exercise_media_assets",
        "presentation",
        existing_type=sa.String(length=6),
        type_=sa.String(length=20),
        existing_nullable=False,
    )
    op.create_check_constraint(
        _PRESENTATION_CONSTRAINT,
        "exercise_media_assets",
        "presentation IN ('male', 'female', 'unspecified')",
    )
    op.add_column(
        "exercise_media_assets",
        sa.Column("source", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "exercise_media_assets",
        sa.Column("source_id", sa.String(length=160), nullable=True),
    )
    op.create_unique_constraint(
        _SOURCE_CONSTRAINT,
        "exercise_media_assets",
        ["source", "source_id"],
    )


def downgrade() -> None:
    op.drop_constraint(_SOURCE_CONSTRAINT, "exercise_media_assets", type_="unique")
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT
                    unspecified.id,
                    COALESCE(male.maximum_sort_order, -1)
                    + ROW_NUMBER() OVER (
                        PARTITION BY unspecified.exercise_id, unspecified.role
                        ORDER BY unspecified.sort_order, unspecified.id
                    ) AS next_sort_order
                FROM exercise_media_assets AS unspecified
                LEFT JOIN LATERAL (
                    SELECT MAX(existing.sort_order) AS maximum_sort_order
                    FROM exercise_media_assets AS existing
                    WHERE existing.exercise_id = unspecified.exercise_id
                      AND existing.role = unspecified.role
                      AND existing.presentation = 'male'
                ) AS male ON TRUE
                WHERE unspecified.presentation = 'unspecified'
            )
            UPDATE exercise_media_assets AS asset
            SET presentation = 'male', sort_order = ranked.next_sort_order
            FROM ranked
            WHERE asset.id = ranked.id
            """
        )
    )
    op.drop_constraint(
        _PRESENTATION_CONSTRAINT,
        "exercise_media_assets",
        type_="check",
    )
    op.alter_column(
        "exercise_media_assets",
        "presentation",
        existing_type=sa.String(length=20),
        type_=sa.String(length=6),
        existing_nullable=False,
    )
    op.create_check_constraint(
        _PRESENTATION_CONSTRAINT,
        "exercise_media_assets",
        "presentation IN ('male', 'female')",
    )
    op.drop_column("exercise_media_assets", "source_id")
    op.drop_column("exercise_media_assets", "source")
