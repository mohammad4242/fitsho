from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.body_photos.enums import (
    BodyPhotoCleanupReason,
    BodyPhotoConsentType,
    BodyPhotoPurpose,
    BodyPhotoSessionState,
    BodyPhotoView,
)
from app.database.base import Base


def enum_values(members: type[StrEnum]) -> list[str]:
    return [member.value for member in members]


class BodyPhotoSession(Base):
    __tablename__ = "body_photo_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cycle_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workout_cycles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    purpose: Mapped[BodyPhotoPurpose] = mapped_column(
        Enum(
            BodyPhotoPurpose,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_body_photo_sessions_purpose_values",
        ),
        nullable=False,
    )
    state: Mapped[BodyPhotoSessionState] = mapped_column(
        Enum(
            BodyPhotoSessionState,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_body_photo_sessions_state_values",
        ),
        default=BodyPhotoSessionState.DRAFT,
        server_default=BodyPhotoSessionState.DRAFT.value,
        nullable=False,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    photos: Mapped[list[BodyPhoto]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="BodyPhoto.created_at",
    )
    consents: Mapped[list[BodyPhotoConsent]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="BodyPhotoConsent.recorded_at",
    )
    storage_cleanups: Mapped[list[BodyPhotoStorageCleanup]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="BodyPhotoStorageCleanup.created_at",
    )


class BodyPhoto(Base):
    __tablename__ = "body_photos"
    __table_args__ = (
        UniqueConstraint("session_id", "view", name="uq_body_photos_session_view"),
        CheckConstraint("byte_size > 0", name="ck_body_photos_byte_size_positive"),
        CheckConstraint("width > 0 AND height > 0", name="ck_body_photos_dimensions_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("body_photo_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    view: Mapped[BodyPhotoView] = mapped_column(
        Enum(
            BodyPhotoView,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_body_photos_view_values",
        ),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(20), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    session: Mapped[BodyPhotoSession] = relationship(back_populates="photos")


class BodyPhotoConsent(Base):
    """Append-only consent event; revocation creates a new row."""

    __tablename__ = "body_photo_consents"
    __table_args__ = (
        CheckConstraint("char_length(version) > 0", name="ck_body_photo_consents_version_present"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("body_photo_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    consent_type: Mapped[BodyPhotoConsentType] = mapped_column(
        Enum(
            BodyPhotoConsentType,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_body_photo_consents_type_values",
        ),
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[BodyPhotoSession] = relationship(back_populates="consents")


class BodyPhotoStorageCleanup(Base):
    """Durable private-object cleanup work retained across storage failures."""

    __tablename__ = "body_photo_storage_cleanups"
    __table_args__ = (
        CheckConstraint(
            "attempts >= 0", name="ck_body_photo_storage_cleanups_attempts_nonnegative"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("body_photo_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    storage_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    reason: Mapped[BodyPhotoCleanupReason] = mapped_column(
        Enum(
            BodyPhotoCleanupReason,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_body_photo_storage_cleanups_reason_values",
        ),
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    session: Mapped[BodyPhotoSession] = relationship(back_populates="storage_cleanups")
