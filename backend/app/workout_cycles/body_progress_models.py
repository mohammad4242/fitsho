from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class WorkoutCycleBodyProgressComparison(Base):
    """Latest auditable start/end body-progress snapshot for one workout cycle."""

    __tablename__ = "workout_cycle_body_progress_comparisons"
    __table_args__ = (
        UniqueConstraint("cycle_id", name="uq_workout_cycle_body_progress_comparisons_cycle"),
        Index(
            "ix_workout_cycle_body_progress_comparisons_user_cycle",
            "user_id",
            "cycle_id",
        ),
        Index("ix_cycle_body_cmp_start_measurement", "start_measurement_id"),
        Index("ix_cycle_body_cmp_end_measurement", "end_measurement_id"),
        Index("ix_cycle_body_cmp_start_session", "start_session_id"),
        Index("ix_cycle_body_cmp_end_session", "end_session_id"),
        Index("ix_cycle_body_cmp_start_analysis", "start_analysis_id"),
        Index("ix_cycle_body_cmp_end_analysis", "end_analysis_id"),
        Index("ix_cycle_body_cmp_start_version", "start_result_version_id"),
        Index("ix_cycle_body_cmp_end_version", "end_result_version_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    cycle_id: Mapped[UUID] = mapped_column(
        ForeignKey("workout_cycles.id", ondelete="RESTRICT"), nullable=False
    )
    start_measurement_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("body_measurements.id", ondelete="SET NULL")
    )
    end_measurement_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("body_measurements.id", ondelete="SET NULL")
    )
    start_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("body_photo_sessions.id", ondelete="SET NULL")
    )
    end_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("body_photo_sessions.id", ondelete="SET NULL")
    )
    start_analysis_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("body_analyses.id", ondelete="SET NULL")
    )
    end_analysis_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("body_analyses.id", ondelete="SET NULL")
    )
    start_result_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("body_analysis_result_versions.id", ondelete="SET NULL")
    )
    end_result_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("body_analysis_result_versions.id", ondelete="SET NULL")
    )
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False, default="1.0")
    comparison_result: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
