"""allow direct APNs notification tokens"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260911_138"
down_revision: str | Sequence[str] | None = "20260911_137"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_notification_device_tokens_provider",
        "notification_device_tokens",
        type_="check",
    )
    op.create_check_constraint(
        "ck_notification_device_tokens_provider",
        "notification_device_tokens",
        "provider IN ('fcm', 'apns')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_notification_device_tokens_provider",
        "notification_device_tokens",
        type_="check",
    )
    op.create_check_constraint(
        "ck_notification_device_tokens_provider",
        "notification_device_tokens",
        "provider IN ('fcm')",
    )
