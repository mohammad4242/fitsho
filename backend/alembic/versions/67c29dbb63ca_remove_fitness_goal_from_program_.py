"""remove fitness_goal from program template

Revision ID: 67c29dbb63ca
Revises: 20260826_113
Create Date: 2026-08-26 18:10:53.471911

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '67c29dbb63ca'
down_revision: Union[str, Sequence[str], None] = '20260826_113'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.drop_constraint('ck_training_program_templates_fitness_goal_values', 'training_program_templates', type_='check')
    op.drop_column('training_program_templates', 'fitness_goal')

def downgrade() -> None:
    op.add_column('training_program_templates', sa.Column('fitness_goal', sa.VARCHAR(length=21), server_default=sa.text("'build_muscle'::character varying"), autoincrement=False, nullable=False))
    op.create_check_constraint('ck_training_program_templates_fitness_goal_values', 'training_program_templates', "fitness_goal::text = ANY (ARRAY['lose_weight'::character varying, 'build_muscle'::character varying, 'body_recomposition'::character varying, 'improve_fitness'::character varying, 'gain_weight'::character varying, 'fat_loss'::character varying, 'strength'::character varying, 'maintain_weight'::character varying, 'bulk'::character varying]::text[])")
