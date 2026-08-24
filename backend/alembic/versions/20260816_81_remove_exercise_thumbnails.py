"""remove exercise thumbnail media"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260816_81"
down_revision: str | Sequence[str] | None = "20260814_80"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ROLE_CONSTRAINT = "ck_exercise_media_assets_role_values"
_TYPE_CONSTRAINT = "ck_exercise_media_assets_role_media_type"


def upgrade() -> None:
    op.execute(sa.text("DELETE FROM exercise_media_assets WHERE role = 'thumbnail'"))
    op.drop_constraint(_TYPE_CONSTRAINT, "exercise_media_assets", type_="check")
    op.drop_constraint(_ROLE_CONSTRAINT, "exercise_media_assets", type_="check")
    op.create_check_constraint(
        _ROLE_CONSTRAINT,
        "exercise_media_assets",
        "role IN ('video')",
    )
    op.create_check_constraint(
        _TYPE_CONSTRAINT,
        "exercise_media_assets",
        "role = 'video' AND media_type = 'video'",
    )


def downgrade() -> None:
    op.drop_constraint(_TYPE_CONSTRAINT, "exercise_media_assets", type_="check")
    op.drop_constraint(_ROLE_CONSTRAINT, "exercise_media_assets", type_="check")
    op.create_check_constraint(
        _ROLE_CONSTRAINT,
        "exercise_media_assets",
        "role IN ('video', 'thumbnail')",
    )
    op.create_check_constraint(
        _TYPE_CONSTRAINT,
        "exercise_media_assets",
        "(role = 'video' AND media_type = 'video') "
        "OR (role = 'thumbnail' AND media_type = 'image')",
    )
