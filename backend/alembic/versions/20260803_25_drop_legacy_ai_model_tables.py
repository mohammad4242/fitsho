"""remove legacy Zen AI model routing tables"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260803_27"
down_revision: str | Sequence[str] | None = "20260803_26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("ai_model_test_runs")
    op.drop_table("ai_routing_settings")
    op.drop_table("ai_models")


def downgrade() -> None:
    raise NotImplementedError("Legacy AI model routing was permanently removed")
