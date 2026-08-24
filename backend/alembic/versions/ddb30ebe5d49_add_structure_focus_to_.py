"""Add structure_focus to TrainingProgramTemplateDay

Revision ID: ddb30ebe5d49
Revises: 20260823_106
Create Date: 2026-08-24 10:04:32.998528

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ddb30ebe5d49'
down_revision: Union[str, Sequence[str], None] = '20260823_106'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'training_program_template_days',
        sa.Column('structure_focus', sa.String(length=100), server_default='full_body', nullable=False)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('training_program_template_days', 'structure_focus')
