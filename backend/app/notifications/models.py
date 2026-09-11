from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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
    nutrition_updates: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class NotificationOutboxEvent(Base):
    __tablename__ = "notification_outbox_events"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "deduplication_key",
            name="uq_notification_outbox_events_user_deduplication",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'processed')",
            name="ck_notification_outbox_events_status",
        ),
        CheckConstraint(
            "char_length(btrim(event_type)) BETWEEN 1 AND 80",
            name="ck_notification_outbox_events_event_type_length",
        ),
        CheckConstraint(
            "char_length(btrim(category)) BETWEEN 1 AND 40",
            name="ck_notification_outbox_events_category_length",
        ),
        CheckConstraint(
            "char_length(btrim(deduplication_key)) BETWEEN 1 AND 200",
            name="ck_notification_outbox_events_deduplication_key_length",
        ),
        Index(
            "ix_notification_outbox_events_status_available_at",
            "status",
            "available_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(200), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", nullable=False
    )
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    deliveries: Mapped[list[NotificationEventDelivery]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class NotificationEventDelivery(Base):
    __tablename__ = "notification_event_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "token_id",
            name="uq_notification_event_deliveries_event_token",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'sent', 'failed', 'dead_letter')",
            name="ck_notification_event_deliveries_status",
        ),
        Index(
            "ix_notification_event_deliveries_token_id_created_at",
            "token_id",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("notification_outbox_events.id", ondelete="CASCADE"), nullable=False
    )
    token_id: Mapped[UUID] = mapped_column(
        ForeignKey("notification_device_tokens.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), default="pending", server_default="pending", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dead_letter_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(256), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    event: Mapped[NotificationOutboxEvent] = relationship(back_populates="deliveries")
