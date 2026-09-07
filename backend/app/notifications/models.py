from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class NotificationDevice(Base):
    __tablename__ = "notification_devices"
    __table_args__ = (
        UniqueConstraint("user_id", "device_id", name="uq_notification_devices_user_device"),
        CheckConstraint(
            "char_length(btrim(device_id)) BETWEEN 1 AND 128",
            name="ck_notification_devices_device_id_length",
        ),
        CheckConstraint(
            "platform IN ('android', 'ios')",
            name="ck_notification_devices_platform",
        ),
        CheckConstraint(
            "char_length(btrim(app_version)) BETWEEN 1 AND 64",
            name="ck_notification_devices_app_version_length",
        ),
        Index("ix_notification_devices_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    device_id: Mapped[str] = mapped_column(String(128), nullable=False)
    platform: Mapped[str] = mapped_column(String(16), nullable=False)
    app_version: Mapped[str] = mapped_column(String(64), nullable=False)
    device_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    tokens: Mapped[list[NotificationDeviceToken]] = relationship(
        back_populates="device",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by=lambda: NotificationDeviceToken.created_at,
    )


class NotificationDeviceToken(Base):
    __tablename__ = "notification_device_tokens"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "token_hash",
            name="uq_notification_device_tokens_provider_hash",
        ),
        CheckConstraint(
            "provider IN ('fcm')",
            name="ck_notification_device_tokens_provider",
        ),
        CheckConstraint(
            "char_length(btrim(token_value)) BETWEEN 1 AND 4096",
            name="ck_notification_device_tokens_value_length",
        ),
        CheckConstraint(
            "char_length(token_hash) = 64",
            name="ck_notification_device_tokens_hash_length",
        ),
        Index(
            "ix_notification_device_tokens_device_provider",
            "device_id",
            "provider",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    device_id: Mapped[UUID] = mapped_column(
        ForeignKey("notification_devices.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # This credential is deliberately never returned by the API or written to logs.
    token_value: Mapped[str] = mapped_column(String(4096), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    invalid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalid_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    device: Mapped[NotificationDevice] = relationship(back_populates="tokens")


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    approved_plans: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    required_reviews: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    body_analysis: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    cycle_reminders: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    physician_decisions: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
