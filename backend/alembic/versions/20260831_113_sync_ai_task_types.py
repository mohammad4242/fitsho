"""Align persisted AI task types with the current task catalog."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260831_113"
down_revision: str | Sequence[str] | None = "20260830_112"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CURRENT_TASK_TYPES = (
    "'workout_plan_generation','body_photo_analysis','progress_comparison',"
    "'food_photo_estimation','food_price_search'"
)
_PREVIOUS_TASK_TYPES = (
    "'workout_plan_generation','body_photo_analysis','progress_comparison',"
    "'specialist_summary','food_photo_estimation'"
)


def upgrade() -> None:
    bind = op.get_bind()
    has_legacy = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM ai_task_configs "
            "WHERE task_type = 'specialist_summary')"
        )
    ).scalar()
    has_current = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM ai_task_configs "
            "WHERE task_type = 'food_price_search')"
        )
    ).scalar()
    if has_legacy and has_current:
        raise RuntimeError(
            "Cannot migrate AI task configs: specialist_summary and food_price_search both exist"
        )

    op.drop_constraint("ck_ai_task_configs_task_type_values", "ai_task_configs", type_="check")
    if has_legacy:
        op.execute(
            sa.text(
                "UPDATE ai_task_configs SET task_type = 'food_price_search' "
                "WHERE task_type = 'specialist_summary'"
            )
        )
    op.create_check_constraint(
        "ck_ai_task_configs_task_type_values",
        "ai_task_configs",
        f"task_type IN ({_CURRENT_TASK_TYPES})",
    )


def downgrade() -> None:
    bind = op.get_bind()
    has_current = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM ai_task_configs "
            "WHERE task_type = 'food_price_search')"
        )
    ).scalar()
    if has_current:
        raise RuntimeError(
            "Cannot downgrade AI task types while food_price_search configuration exists"
        )
    op.drop_constraint("ck_ai_task_configs_task_type_values", "ai_task_configs", type_="check")
    op.create_check_constraint(
        "ck_ai_task_configs_task_type_values",
        "ai_task_configs",
        f"task_type IN ({_PREVIOUS_TASK_TYPES})",
    )
