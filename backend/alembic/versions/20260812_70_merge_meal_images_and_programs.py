"""merge meal catalogue images and nutrition programs"""

from collections.abc import Sequence

revision: str = "20260812_70"
down_revision: str | Sequence[str] | None = ("20260812_69", "20260812_67m")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
