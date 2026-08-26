"""Classify training program structures by family and split type.

Revision ID: 20260826_112
Revises: 20260826_111
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260826_112"
down_revision: str | Sequence[str] | None = "20260826_111"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_UPPER_LOWER_SLUGS = (
    "4d-upper-lower-2x",
    "4d-3-upper-1-lower",
    "4d-3-lower-1-upper",
)
_PPL_SLUGS = (
    "5d-ppl-upper-lower",
    "6d-ppl-2x",
    "6d-ppl-specialization",
)
_BODY_PART_SLUGS = (
    "4d-push-pull-quads-posterior",
    "5d-classic-body-part",
    "5d-chest-spec-body-part",
    "5d-back-spec-body-part",
    "5d-leg-spec-body-part",
    "6d-advanced-body-part",
)


def upgrade() -> None:
    op.add_column(
        "training_program_structures",
        sa.Column("family", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "training_program_structures",
        sa.Column("split_type", sa.String(length=20), nullable=True),
    )

    structures = sa.table(
        "training_program_structures",
        sa.column("slug", sa.String()),
        sa.column("family", sa.String()),
        sa.column("split_type", sa.String()),
    )
    bind = op.get_bind()
    bind.execute(
        structures.update()
        .where(structures.c.slug.in_(_UPPER_LOWER_SLUGS))
        .values(family="upper_lower")
    )
    bind.execute(
        structures.update()
        .where(structures.c.slug.in_(_PPL_SLUGS))
        .values(family="split", split_type="ppl")
    )
    bind.execute(
        structures.update()
        .where(structures.c.slug.in_(_BODY_PART_SLUGS))
        .values(family="split", split_type="body_part")
    )

    op.create_check_constraint(
        "ck_training_program_structures_family_values",
        "training_program_structures",
        "family IS NULL OR family IN ('upper_lower', 'split')",
    )
    op.create_check_constraint(
        "ck_training_program_structures_split_type_values",
        "training_program_structures",
        "split_type IS NULL OR split_type IN ('ppl', 'body_part')",
    )
    op.create_check_constraint(
        "ck_training_program_structures_family_classification",
        "training_program_structures",
        "(days_per_week BETWEEN 2 AND 3 AND family IS NULL AND split_type IS NULL) OR "
        "(days_per_week BETWEEN 4 AND 6 AND "
        "((family = 'upper_lower' AND split_type IS NULL) OR "
        "(family = 'split' AND split_type IN ('ppl', 'body_part'))))",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_training_program_structures_family_classification",
        "training_program_structures",
        type_="check",
    )
    op.drop_constraint(
        "ck_training_program_structures_split_type_values",
        "training_program_structures",
        type_="check",
    )
    op.drop_constraint(
        "ck_training_program_structures_family_values",
        "training_program_structures",
        type_="check",
    )
    op.drop_column("training_program_structures", "split_type")
    op.drop_column("training_program_structures", "family")
