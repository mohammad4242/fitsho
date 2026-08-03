from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.body_analysis.enums import BodyAnalysisStatus
from app.body_photos.models import BodyPhotoSession
from app.database.base import Base


def enum_values(members: type[StrEnum]) -> list[str]:
    return [member.value for member in members]


class BodyAnalysis(Base):
    __tablename__ = "body_analyses"
    __table_args__ = (
        UniqueConstraint("session_id", "revision", name="uq_body_analyses_session_revision"),
        CheckConstraint("revision > 0", name="ck_body_analyses_revision_positive"),
        CheckConstraint("attempt_count >= 0", name="ck_body_analyses_attempt_count_nonnegative"),
        CheckConstraint(
            "overall_confidence IS NULL OR "
            "(overall_confidence >= 0 AND overall_confidence <= 1)",
            name="ck_body_analyses_overall_confidence_range",
        ),
        CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_body_analyses_input_tokens_nonnegative",
        ),
        CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_body_analyses_output_tokens_nonnegative",
        ),
        CheckConstraint(
            "request_cost IS NULL OR request_cost >= 0",
            name="ck_body_analyses_request_cost_nonnegative",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("body_photo_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    replaces_analysis_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("body_analyses.id", ondelete="SET NULL")
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model_id: Mapped[str] = mapped_column(String(300), nullable=False)
    fallback_model_id: Mapped[str | None] = mapped_column(String(300))
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[BodyAnalysisStatus] = mapped_column(
        Enum(
            BodyAnalysisStatus,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_body_analyses_status_values",
        ),
        default=BodyAnalysisStatus.QUEUED,
        server_default=BodyAnalysisStatus.QUEUED.value,
        nullable=False,
    )
    raw_result: Mapped[dict[str, object] | None] = mapped_column(JSON)
    normalized_result: Mapped[dict[str, object] | None] = mapped_column(JSON)
    overall_confidence: Mapped[float | None] = mapped_column(Float)
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(String(500))
    provider_request_id: Mapped[str | None] = mapped_column(String(160))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    request_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    attempt_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    session: Mapped[BodyPhotoSession] = relationship()
    replaces_analysis: Mapped[BodyAnalysis | None] = relationship(remote_side="BodyAnalysis.id")
