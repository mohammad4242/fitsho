"""harden body photo crop evidence and cleanup"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_18a"
down_revision: str | Sequence[str] | None = "20260803_18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("body_photos", sa.Column("crop_original_height", sa.Integer(), nullable=True))
    op.add_column("body_photos", sa.Column("crop_top", sa.Integer(), nullable=True))
    op.add_column("body_photos", sa.Column("crop_bottom", sa.Integer(), nullable=True))
    op.add_column("body_photos", sa.Column("processed_sha256", sa.String(length=64), nullable=True))
    op.add_column(
        "body_photos",
        sa.Column("crop_evidence_sha256", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        "ck_body_photos_crop_original_height_positive",
        "body_photos",
        "crop_original_height IS NULL OR crop_original_height > 0",
    )
    op.create_check_constraint(
        "ck_body_photos_crop_top_nonnegative",
        "body_photos",
        "crop_top IS NULL OR crop_top >= 0",
    )
    op.create_check_constraint(
        "ck_body_photos_crop_bottom_after_top",
        "body_photos",
        "crop_bottom IS NULL OR crop_bottom > crop_top",
    )
    op.execute("UPDATE body_photos SET crop_geometry_verified = false")
    op.create_check_constraint(
        "ck_body_photos_verified_crop_evidence_complete",
        "body_photos",
        "NOT crop_geometry_verified OR "
        "(crop_original_height IS NOT NULL AND crop_top IS NOT NULL AND "
        "crop_bottom IS NOT NULL AND crop_bottom <= crop_original_height AND "
        "crop_bottom - crop_top = height AND char_length(processed_sha256) = 64 AND "
        "char_length(crop_evidence_sha256) = 64)",
    )

    op.create_table(
        "body_photo_storage_cleanups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(length=160), nullable=False),
        sa.Column(
            "reason",
            sa.Enum(
                "replacement",
                "session_delete",
                name="ck_body_photo_storage_cleanups_reason_values",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name="ck_body_photo_storage_cleanups_attempts_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["body_photo_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        "ix_body_photo_storage_cleanups_session_id",
        "body_photo_storage_cleanups",
        ["session_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_body_photo_storage_cleanups_session_id",
        table_name="body_photo_storage_cleanups",
    )
    op.drop_table("body_photo_storage_cleanups")
    op.drop_constraint(
        "ck_body_photos_verified_crop_evidence_complete",
        "body_photos",
        type_="check",
    )
    op.drop_constraint(
        "ck_body_photos_crop_bottom_after_top",
        "body_photos",
        type_="check",
    )
    op.drop_constraint(
        "ck_body_photos_crop_top_nonnegative",
        "body_photos",
        type_="check",
    )
    op.drop_constraint(
        "ck_body_photos_crop_original_height_positive",
        "body_photos",
        type_="check",
    )
    op.drop_column("body_photos", "crop_evidence_sha256")
    op.drop_column("body_photos", "processed_sha256")
    op.drop_column("body_photos", "crop_bottom")
    op.drop_column("body_photos", "crop_top")
    op.drop_column("body_photos", "crop_original_height")
