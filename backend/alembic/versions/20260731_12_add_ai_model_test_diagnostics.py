"""add AI model test diagnostics

Revision ID: 20260731_12
Revises: 20260731_11
"""

import sqlalchemy as sa

from alembic import op

revision = "20260731_12"
down_revision = "20260731_11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ai_model_test_runs",
        sa.Column("provider_status_code", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ai_model_test_runs",
        sa.Column("provider_error_type", sa.String(length=80), nullable=True),
    )
    op.add_column(
        "ai_model_test_runs",
        sa.Column("provider_error_message", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ai_model_test_runs", "provider_error_message")
    op.drop_column("ai_model_test_runs", "provider_error_type")
    op.drop_column("ai_model_test_runs", "provider_status_code")
