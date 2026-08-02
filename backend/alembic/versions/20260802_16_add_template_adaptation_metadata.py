"""add training template adaptation metadata"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "20260802_16"
down_revision = "20260802_15"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "training_program_template_slots",
        sa.Column(
            "adaptation_priority",
            sa.String(length=12),
            server_default="core",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_training_program_template_slots_priority_values",
        "training_program_template_slots",
        "adaptation_priority IN ('core', 'accessory', 'optional')",
    )
    op.add_column(
        "training_program_template_slots",
        sa.Column("superset_group", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("training_program_template_slots", "superset_group")
    op.drop_constraint(
        "ck_training_program_template_slots_priority_values",
        "training_program_template_slots",
        type_="check",
    )
    op.drop_column("training_program_template_slots", "adaptation_priority")
