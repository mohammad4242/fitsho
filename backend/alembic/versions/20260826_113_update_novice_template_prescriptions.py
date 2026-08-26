"""Update legacy novice template prescriptions without replacing admin edits.

Revision ID: 20260826_113
Revises: 20260826_112
Create Date: 2026-08-26
"""

from collections.abc import Sequence

from sqlalchemy.orm import Session

from alembic import op
from app.training_templates.service import upgrade_novice_template_prescriptions

revision: str = "20260826_113"
down_revision: str | Sequence[str] | None = "20260826_112"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    session = Session(bind=bind, join_transaction_mode="create_savepoint")
    try:
        upgrade_novice_template_prescriptions(session)
    finally:
        session.close()


def downgrade() -> None:
    # The migration intentionally does not reverse prescriptions because that could
    # overwrite an admin edit made after the upgrade.
    pass
