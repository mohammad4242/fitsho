from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def enum_values(members: type[StrEnum]) -> list[str]:
    return [member.value for member in members]


class ZenApiKind(StrEnum):
    RESPONSES = "responses"
    CHAT_COMPLETIONS = "chat_completions"
    MESSAGES = "messages"
    GEMINI = "gemini"


class BillingClass(StrEnum):
    FREE = "free"
    PAID = "paid"


class RoutingMode(StrEnum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"


class AiModel(Base):
    __tablename__ = "ai_models"
    __table_args__ = (
        CheckConstraint("priority >= 0", name="ck_ai_models_priority_nonnegative"),
        CheckConstraint(
            "NOT classification_required OR "
            "(api_kind IS NULL AND billing_class IS NULL AND NOT is_enabled)",
            name="ck_ai_models_unclassified_disabled",
        ),
        CheckConstraint(
            "NOT is_enabled OR "
            "(api_kind IS NOT NULL AND billing_class IS NOT NULL AND NOT classification_required)",
            name="ck_ai_models_enabled_classified",
        ),
        Index(
            "ix_ai_models_automatic_route",
            "is_enabled",
            "billing_class",
            "priority",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    model_id: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    api_kind: Mapped[ZenApiKind | None] = mapped_column(
        Enum(
            ZenApiKind,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_ai_models_api_kind_values",
        )
    )
    billing_class: Mapped[BillingClass | None] = mapped_column(
        Enum(
            BillingClass,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_ai_models_billing_class_values",
        )
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    priority: Mapped[int] = mapped_column(
        Integer, default=1000, server_default="1000", nullable=False
    )
    is_custom: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    classification_required: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    last_error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AiRoutingSettings(Base):
    __tablename__ = "ai_routing_settings"
    __table_args__ = (CheckConstraint("id = 1", name="ck_ai_routing_settings_singleton"),)

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    mode: Mapped[RoutingMode] = mapped_column(
        Enum(
            RoutingMode,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_ai_routing_settings_mode_values",
        ),
        default=RoutingMode.MANUAL,
        server_default=RoutingMode.MANUAL.value,
        nullable=False,
    )
    manual_model_id: Mapped[UUID | None] = mapped_column(ForeignKey("ai_models.id"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
