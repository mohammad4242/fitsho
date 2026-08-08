"""add physician queue and secure laboratory metadata"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260809_48"
down_revision: str | Sequence[str] | None = "20260809_47"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_user_specialist_roles_role_values", "user_specialist_roles", type_="check"
    )
    op.alter_column(
        "user_specialist_roles",
        "role",
        existing_type=sa.String(length=6),
        type_=sa.String(length=16),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_user_specialist_roles_role_values",
        "user_specialist_roles",
        "role IN ('coach','doctor','physician')",
    )
    review_columns = (
        sa.Column("priority", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("assigned_at", sa.DateTime(timezone=True)),
        sa.Column("review_started_at", sa.DateTime(timezone=True)),
        sa.Column("target_review_by", sa.DateTime(timezone=True)),
        sa.Column("reassignment_count", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("internal_notes", sa.String(4000)),
        sa.Column("structured_change_summary", sa.JSON(), nullable=False, server_default="[]"),
    )
    for column in review_columns:
        op.add_column("nutrition_plan_physician_reviews", column)
    document_columns = (
        sa.Column("test_date", sa.Date()),
        sa.Column("laboratory_name", sa.String(160)),
        sa.Column("user_note", sa.String(1000)),
        sa.Column("category", sa.String(80)),
        sa.Column("review_status", sa.String(24), nullable=False, server_default="unreviewed"),
        sa.Column(
            "request_id",
            sa.Uuid(),
            sa.ForeignKey("nutrition_lab_requests.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "assigned_physician_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("retained_until", sa.Date()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    for column in document_columns:
        op.add_column("nutrition_lab_documents", column)
    op.create_check_constraint(
        "ck_nutrition_lab_document_review_status",
        "nutrition_lab_documents",
        "review_status IN ('unreviewed','reviewed','rejected')",
    )
    op.create_table(
        "nutrition_review_audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "review_id",
            sa.Uuid(),
            sa.ForeignKey("nutrition_plan_physician_reviews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("metadata_snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("nutrition_review_audit_events")
    op.drop_constraint(
        "ck_nutrition_lab_document_review_status", "nutrition_lab_documents", type_="check"
    )
    for name in (
        "updated_at",
        "retained_until",
        "assigned_physician_user_id",
        "request_id",
        "review_status",
        "category",
        "user_note",
        "laboratory_name",
        "test_date",
    ):
        op.drop_column("nutrition_lab_documents", name)
    for name in (
        "structured_change_summary",
        "internal_notes",
        "reassignment_count",
        "target_review_by",
        "review_started_at",
        "assigned_at",
        "priority",
    ):
        op.drop_column("nutrition_plan_physician_reviews", name)
    op.drop_constraint(
        "ck_user_specialist_roles_role_values", "user_specialist_roles", type_="check"
    )
    op.execute("UPDATE user_specialist_roles SET role = 'doctor' WHERE role = 'physician'")
    op.alter_column(
        "user_specialist_roles",
        "role",
        existing_type=sa.String(length=16),
        type_=sa.String(length=6),
        existing_nullable=False,
    )
    op.create_check_constraint(
        "ck_user_specialist_roles_role_values",
        "user_specialist_roles",
        "role IN ('coach','doctor')",
    )
