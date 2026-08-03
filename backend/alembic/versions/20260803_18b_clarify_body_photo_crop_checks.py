"""clarify body photo crop checks and rollback cleanup"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_18b"
down_revision: str | Sequence[str] | None = "20260803_18a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_body_photos_verified_crop_evidence_complete",
        "body_photos",
        type_="check",
    )
    op.add_column(
        "body_photos",
        sa.Column(
            "client_crop_confirmed",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.alter_column(
        "body_photos",
        "crop_geometry_verified",
        new_column_name="server_geometry_checked",
    )
    op.execute("UPDATE body_photos SET server_geometry_checked = false")
    op.create_check_constraint(
        "ck_body_photos_checked_crop_evidence_complete",
        "body_photos",
        "NOT server_geometry_checked OR "
        "(client_crop_confirmed AND crop_original_height IS NOT NULL AND "
        "crop_top IS NOT NULL AND crop_bottom IS NOT NULL AND "
        "crop_bottom <= crop_original_height AND crop_bottom - crop_top = height AND "
        "char_length(processed_sha256) = 64 AND char_length(crop_evidence_sha256) = 64)",
    )

    op.drop_constraint(
        "ck_body_photo_storage_cleanups_reason_values",
        "body_photo_storage_cleanups",
        type_="check",
    )
    op.alter_column(
        "body_photo_storage_cleanups",
        "reason",
        existing_type=sa.String(length=14),
        type_=sa.String(length=22),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_body_photo_storage_cleanups_reason_values",
        "body_photo_storage_cleanups",
        "reason IN ('replacement', 'session_delete', 'failed_upload_rollback')",
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM body_photo_storage_cleanups WHERE reason = 'failed_upload_rollback'"
    )
    op.drop_constraint(
        "ck_body_photo_storage_cleanups_reason_values",
        "body_photo_storage_cleanups",
        type_="check",
    )
    op.alter_column(
        "body_photo_storage_cleanups",
        "reason",
        existing_type=sa.String(length=22),
        type_=sa.String(length=14),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_body_photo_storage_cleanups_reason_values",
        "body_photo_storage_cleanups",
        "reason IN ('replacement', 'session_delete')",
    )

    op.drop_constraint(
        "ck_body_photos_checked_crop_evidence_complete",
        "body_photos",
        type_="check",
    )
    op.alter_column(
        "body_photos",
        "server_geometry_checked",
        new_column_name="crop_geometry_verified",
    )
    op.create_check_constraint(
        "ck_body_photos_verified_crop_evidence_complete",
        "body_photos",
        "NOT crop_geometry_verified OR "
        "(crop_original_height IS NOT NULL AND crop_top IS NOT NULL AND "
        "crop_bottom IS NOT NULL AND crop_bottom <= crop_original_height AND "
        "crop_bottom - crop_top = height AND char_length(processed_sha256) = 64 AND "
        "char_length(crop_evidence_sha256) = 64)",
    )
    op.drop_column("body_photos", "client_crop_confirmed")
