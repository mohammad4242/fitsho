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

from app.body_analysis.enums import (
    BodyAnalysisResultSource,
    BodyAnalysisReviewDecision,
    BodyAnalysisReviewerRole,
    BodyAnalysisStatus,
    SpecialistRole,
)
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
            "overall_confidence IS NULL OR (overall_confidence >= 0 AND overall_confidence <= 1)",
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
    visual_result: Mapped[dict[str, object] | None] = mapped_column(JSON)
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
    result_versions: Mapped[list[BodyAnalysisResultVersion]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="BodyAnalysisResultVersion.version",
    )
    reviews: Mapped[list[BodyAnalysisReview]] = relationship(
        back_populates="analysis",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="BodyAnalysisReview.created_at",
    )


class BodyAnalysisResultVersion(Base):
    """Append-only normalized result history, independent of provider envelopes."""

    __tablename__ = "body_analysis_result_versions"
    __table_args__ = (
        UniqueConstraint(
            "analysis_id", "version", name="uq_body_analysis_result_versions_analysis_version"
        ),
        CheckConstraint("version > 0", name="ck_body_analysis_result_versions_version_positive"),
        CheckConstraint(
            "overall_confidence >= 0 AND overall_confidence <= 1",
            name="ck_body_analysis_result_versions_confidence_range",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    analysis_id: Mapped[UUID] = mapped_column(
        ForeignKey("body_analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    replaces_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("body_analysis_result_versions.id", ondelete="SET NULL")
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[BodyAnalysisResultSource] = mapped_column(
        Enum(
            BodyAnalysisResultSource,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_body_analysis_result_versions_source_values",
        ),
        nullable=False,
    )
    normalized_result: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    visual_result: Mapped[dict[str, object] | None] = mapped_column(JSON)
    overall_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    analysis: Mapped[BodyAnalysis] = relationship(back_populates="result_versions")
    replaces_version: Mapped[BodyAnalysisResultVersion | None] = relationship(
        remote_side="BodyAnalysisResultVersion.id"
    )


class BodyAnalysisReview(Base):
    """Append-only specialist decision for one immutable result version."""

    __tablename__ = "body_analysis_reviews"
    __table_args__ = (
        CheckConstraint(
            "notes IS NULL OR char_length(notes) > 0",
            name="ck_body_analysis_reviews_notes_nonempty",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    analysis_id: Mapped[UUID] = mapped_column(
        ForeignKey("body_analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    result_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("body_analysis_result_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    reviewer_role: Mapped[BodyAnalysisReviewerRole] = mapped_column(
        Enum(
            BodyAnalysisReviewerRole,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_body_analysis_reviews_role_values",
        ),
        nullable=False,
    )
    decision: Mapped[BodyAnalysisReviewDecision] = mapped_column(
        Enum(
            BodyAnalysisReviewDecision,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_body_analysis_reviews_decision_values",
        ),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    analysis: Mapped[BodyAnalysis] = relationship(back_populates="reviews")
    result_version: Mapped[BodyAnalysisResultVersion] = relationship()


class UserSpecialistRole(Base):
    """Explicit reviewer authorization; admin status is not a clinical role."""

    __tablename__ = "user_specialist_roles"
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[SpecialistRole] = mapped_column(
        Enum(
            SpecialistRole,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_user_specialist_roles_role_values",
        ),
        primary_key=True,
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
