"""persist cycle start and end body progress comparisons"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260818_95"
down_revision: str | Sequence[str] | None = "20260818_94"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workout_cycle_body_progress_comparisons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("cycle_id", sa.Uuid(), nullable=False),
        sa.Column("start_measurement_id", sa.Uuid(), nullable=True),
        sa.Column("end_measurement_id", sa.Uuid(), nullable=True),
        sa.Column("start_session_id", sa.Uuid(), nullable=True),
        sa.Column("end_session_id", sa.Uuid(), nullable=True),
        sa.Column("start_analysis_id", sa.Uuid(), nullable=True),
        sa.Column("end_analysis_id", sa.Uuid(), nullable=True),
        sa.Column("start_result_version_id", sa.Uuid(), nullable=True),
        sa.Column("end_result_version_id", sa.Uuid(), nullable=True),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("comparison_result", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cycle_id"], ["workout_cycles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["start_measurement_id"], ["body_measurements.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["end_measurement_id"], ["body_measurements.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["start_session_id"], ["body_photo_sessions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["end_session_id"], ["body_photo_sessions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["start_analysis_id"], ["body_analyses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["end_analysis_id"], ["body_analyses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["start_result_version_id"],
            ["body_analysis_result_versions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["end_result_version_id"],
            ["body_analysis_result_versions.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cycle_id", name="uq_workout_cycle_body_progress_comparisons_cycle"),
    )
    op.create_index(
        "ix_workout_cycle_body_progress_comparisons_user_cycle",
        "workout_cycle_body_progress_comparisons",
        ["user_id", "cycle_id"],
    )
    for column in (
        "start_measurement_id",
        "end_measurement_id",
        "start_session_id",
        "end_session_id",
        "start_analysis_id",
        "end_analysis_id",
        "start_result_version_id",
        "end_result_version_id",
    ):
        short_name = {
            "start_measurement_id": "ix_cycle_body_cmp_start_measurement",
            "end_measurement_id": "ix_cycle_body_cmp_end_measurement",
            "start_session_id": "ix_cycle_body_cmp_start_session",
            "end_session_id": "ix_cycle_body_cmp_end_session",
            "start_analysis_id": "ix_cycle_body_cmp_start_analysis",
            "end_analysis_id": "ix_cycle_body_cmp_end_analysis",
            "start_result_version_id": "ix_cycle_body_cmp_start_version",
            "end_result_version_id": "ix_cycle_body_cmp_end_version",
        }[column]
        op.create_index(
            short_name,
            "workout_cycle_body_progress_comparisons",
            [column],
        )


def downgrade() -> None:
    for column in (
        "end_result_version_id",
        "start_result_version_id",
        "end_analysis_id",
        "start_analysis_id",
        "end_session_id",
        "start_session_id",
        "end_measurement_id",
        "start_measurement_id",
    ):
        short_name = {
            "start_measurement_id": "ix_cycle_body_cmp_start_measurement",
            "end_measurement_id": "ix_cycle_body_cmp_end_measurement",
            "start_session_id": "ix_cycle_body_cmp_start_session",
            "end_session_id": "ix_cycle_body_cmp_end_session",
            "start_analysis_id": "ix_cycle_body_cmp_start_analysis",
            "end_analysis_id": "ix_cycle_body_cmp_end_analysis",
            "start_result_version_id": "ix_cycle_body_cmp_start_version",
            "end_result_version_id": "ix_cycle_body_cmp_end_version",
        }[column]
        op.drop_index(
            short_name,
            table_name="workout_cycle_body_progress_comparisons",
        )
    op.drop_index(
        "ix_workout_cycle_body_progress_comparisons_user_cycle",
        table_name="workout_cycle_body_progress_comparisons",
    )
    op.drop_table("workout_cycle_body_progress_comparisons")
