"""remove obsolete body photo crop evidence"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260814_77"
down_revision: str | Sequence[str] | None = "20260813_76"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINTS = (
    "ck_body_photos_checked_crop_evidence_complete",
    "ck_body_photos_crop_bottom_after_top",
    "ck_body_photos_crop_top_nonnegative",
    "ck_body_photos_crop_original_height_positive",
    "ck_body_photos_crop_confidence_range",
)

_COLUMNS = (
    "crop_evidence_sha256",
    "processed_sha256",
    "crop_bottom",
    "crop_top",
    "crop_original_height",
    "server_geometry_checked",
    "client_crop_confirmed",
    "crop_confidence",
)


def upgrade() -> None:
    for name in _CONSTRAINTS:
        op.drop_constraint(name, "body_photos", type_="check")
    for name in _COLUMNS:
        op.drop_column("body_photos", name)


def downgrade() -> None:
    op.add_column(
        "body_photos",
        sa.Column("crop_confidence", sa.Float(), server_default="0", nullable=False),
    )
    op.add_column(
        "body_photos",
        sa.Column("client_crop_confirmed", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "body_photos",
        sa.Column(
            "server_geometry_checked",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column("body_photos", sa.Column("crop_original_height", sa.Integer()))
    op.add_column("body_photos", sa.Column("crop_top", sa.Integer()))
    op.add_column("body_photos", sa.Column("crop_bottom", sa.Integer()))
    op.add_column("body_photos", sa.Column("processed_sha256", sa.String(length=64)))
    op.add_column("body_photos", sa.Column("crop_evidence_sha256", sa.String(length=64)))
    op.create_check_constraint(
        "ck_body_photos_crop_confidence_range",
        "body_photos",
        "crop_confidence >= 0 AND crop_confidence <= 1",
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
    op.create_check_constraint(
        "ck_body_photos_checked_crop_evidence_complete",
        "body_photos",
        "NOT server_geometry_checked OR "
        "(client_crop_confirmed AND crop_original_height IS NOT NULL AND "
        "crop_top IS NOT NULL AND crop_bottom IS NOT NULL AND "
        "crop_bottom <= crop_original_height AND crop_bottom - crop_top = height AND "
        "char_length(processed_sha256) = 64 AND char_length(crop_evidence_sha256) = 64)",
    )
