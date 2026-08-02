"""create private body photo sessions"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260803_18"
down_revision: str | Sequence[str] | None = "20260802_17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "body_photo_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "purpose",
            sa.Enum(
                "initial_plan",
                "cycle_completion",
                "progress_check",
                name="ck_body_photo_sessions_purpose_values",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "state",
            sa.Enum(
                "draft",
                "awaiting_consent",
                "uploading",
                "uploaded",
                "queued",
                "validating",
                "analyzing",
                "review_pending",
                "completed",
                "failed",
                "deleted",
                name="ck_body_photo_sessions_state_values",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_body_photo_sessions_user_id", "body_photo_sessions", ["user_id"])

    op.create_table(
        "body_photos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column(
            "view",
            sa.Enum(
                "front",
                "side",
                "back",
                name="ck_body_photos_view_values",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("storage_key", sa.String(length=160), nullable=False),
        sa.Column("mime_type", sa.String(length=20), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("crop_confidence", sa.Float(), nullable=False),
        sa.Column(
            "crop_geometry_verified", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("byte_size > 0", name="ck_body_photos_byte_size_positive"),
        sa.CheckConstraint(
            "crop_confidence >= 0 AND crop_confidence <= 1",
            name="ck_body_photos_crop_confidence_range",
        ),
        sa.CheckConstraint(
            "width > 0 AND height > 0",
            name="ck_body_photos_dimensions_positive",
        ),
        sa.ForeignKeyConstraint(["session_id"], ["body_photo_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "view", name="uq_body_photos_session_view"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_body_photos_session_id", "body_photos", ["session_id"])

    op.create_table(
        "body_photo_consents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "consent_type",
            sa.Enum(
                "operational_processing",
                "model_training",
                name="ck_body_photo_consents_type_values",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column(
            "recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "char_length(version) > 0",
            name="ck_body_photo_consents_version_present",
        ),
        sa.ForeignKeyConstraint(["session_id"], ["body_photo_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_body_photo_consents_session_id", "body_photo_consents", ["session_id"])
    op.create_index("ix_body_photo_consents_user_id", "body_photo_consents", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_body_photo_consents_user_id", table_name="body_photo_consents")
    op.drop_index("ix_body_photo_consents_session_id", table_name="body_photo_consents")
    op.drop_table("body_photo_consents")
    op.drop_index("ix_body_photos_session_id", table_name="body_photos")
    op.drop_table("body_photos")
    op.drop_index("ix_body_photo_sessions_user_id", table_name="body_photo_sessions")
    op.drop_table("body_photo_sessions")
