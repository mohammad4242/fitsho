from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class BodyProgressComparison(Base):
    """Append-only comparison for one immutable current analysis result version."""

    __tablename__ = "body_progress_comparisons"
    __table_args__ = (
        UniqueConstraint(
            "current_result_version_id",
            name="uq_body_progress_comparisons_current_result",
        ),
        UniqueConstraint(
            "current_session_id",
            "comparison_version",
            name="uq_body_progress_comparisons_session_version",
        ),
        CheckConstraint(
            "comparison_version > 0",
            name="ck_body_progress_comparisons_version_positive",
        ),
        CheckConstraint(
            "previous_session_id <> current_session_id",
            name="ck_body_progress_comparisons_distinct_sessions",
        ),
        CheckConstraint(
            "char_length(schema_version) > 0",
            name="ck_body_progress_comparisons_schema_version_present",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    previous_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("body_photo_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    current_session_id: Mapped[UUID] = mapped_column(
        ForeignKey("body_photo_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    previous_result_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("body_analysis_result_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    current_result_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("body_analysis_result_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    previous_feedback_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workout_cycle_feedback.id", ondelete="SET NULL")
    )
    current_feedback_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workout_cycle_feedback.id", ondelete="SET NULL")
    )
    comparison_version: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    normalized_result: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    quality_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    context_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
