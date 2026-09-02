from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.body_analysis.admin_config.enums import (
    AIAgentName,
    AIAgentServiceProxySource,
    AIAuditAction,
    AIExecutionBackend,
    AIProviderName,
    AITaskType,
)
from app.database.base import Base


def enum_values(members: type[StrEnum]) -> list[str]:
    return [member.value for member in members]


class AIProviderCredential(Base):
    __tablename__ = "ai_provider_credentials"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider: Mapped[AIProviderName] = mapped_column(
        Enum(
            AIProviderName,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_ai_provider_credentials_provider_values",
        ),
        unique=True,
        nullable=False,
    )
    encrypted_api_key: Mapped[str] = mapped_column(String(2048), nullable=False)
    key_last_four: Mapped[str] = mapped_column(String(4), nullable=False)
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AIAgentServiceProxySetting(Base):
    __tablename__ = "ai_agent_service_proxy_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_ai_agent_service_proxy_settings_singleton"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    source: Mapped[AIAgentServiceProxySource] = mapped_column(
        Enum(
            AIAgentServiceProxySource,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_ai_agent_service_proxy_settings_source_values",
        ),
        default=AIAgentServiceProxySource.DEPLOYMENT_DEFAULT,
        server_default=AIAgentServiceProxySource.DEPLOYMENT_DEFAULT.value,
        nullable=False,
    )
    encrypted_proxy_url: Mapped[str | None] = mapped_column(String(2048))
    masked_proxy_url: Mapped[str | None] = mapped_column(String(500))
    last_applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_apply_error: Mapped[str | None] = mapped_column(String(500))
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AITaskConfig(Base):
    __tablename__ = "ai_task_configs"
    __table_args__ = (
        CheckConstraint("temperature >= 0 AND temperature <= 2", name="ck_ai_task_temp_range"),
        CheckConstraint("max_output_tokens > 0", name="ck_ai_task_tokens_positive"),
        CheckConstraint("timeout_seconds > 0", name="ck_ai_task_timeout_positive"),
        CheckConstraint(
            "minimum_confidence >= 0 AND minimum_confidence <= 1",
            name="ck_ai_task_confidence_range",
        ),
        CheckConstraint(
            "max_cost_per_request IS NULL OR max_cost_per_request >= 0",
            name="ck_ai_task_cost_nonnegative",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    task_type: Mapped[AITaskType] = mapped_column(
        Enum(
            AITaskType,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_ai_task_configs_task_type_values",
        ),
        unique=True,
        nullable=False,
    )
    provider: Mapped[AIProviderName] = mapped_column(
        Enum(
            AIProviderName,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_ai_task_configs_provider_values",
        ),
        nullable=False,
    )
    execution_backend: Mapped[AIExecutionBackend] = mapped_column(
        Enum(
            AIExecutionBackend,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_ai_task_configs_execution_backend_values",
        ),
        nullable=False,
        default=AIExecutionBackend.API,
        server_default="api",
    )
    agent_name: Mapped[AIAgentName | None] = mapped_column(
        Enum(
            AIAgentName,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_ai_task_configs_agent_name_values",
        )
    )
    agent_model_id: Mapped[str | None] = mapped_column(String(300))
    agent_profile_id: Mapped[str | None] = mapped_column(String(200))
    primary_model_id: Mapped[str | None] = mapped_column(String(300))
    fallback_model_ids: Mapped[list[str]] = mapped_column(
        JSON, default=list, server_default=text("'[]'::json"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    temperature: Mapped[float] = mapped_column(default=0.0, server_default="0", nullable=False)
    max_output_tokens: Mapped[int] = mapped_column(
        Integer, default=4096, server_default="4096", nullable=False
    )
    timeout_seconds: Mapped[int] = mapped_column(
        Integer, default=45, server_default="45", nullable=False
    )
    minimum_confidence: Mapped[float] = mapped_column(
        default=0.7, server_default="0.7", nullable=False
    )
    max_cost_per_request: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    routing_restrictions: Mapped[list[str]] = mapped_column(
        JSON, default=list, server_default=text("'[]'::json"), nullable=False
    )
    last_successful_connection_test_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_model_catalog_refresh_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    last_error_message: Mapped[str | None] = mapped_column(String(500))
    updated_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AIAgentProfileVerification(Base):
    __tablename__ = "ai_agent_profile_verifications"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "task_type",
            name="uq_ai_agent_profile_verifications_profile_task",
        ),
        CheckConstraint(
            "status IN ('passed', 'failed')",
            name="ck_ai_agent_profile_verifications_status_values",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    profile_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    task_type: Mapped[AITaskType] = mapped_column(
        Enum(
            AITaskType,
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            values_callable=enum_values,
        ),
        nullable=False,
    )
    profile_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column()
    error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))


class AIModelCatalogEntry(Base):
    __tablename__ = "ai_model_catalog_entries"
    __table_args__ = (
        UniqueConstraint("provider", "model_id", name="uq_ai_model_catalog_provider_model"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    provider: Mapped[AIProviderName] = mapped_column(
        Enum(
            AIProviderName,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_ai_model_catalog_provider_values",
        ),
        nullable=False,
    )
    model_id: Mapped[str] = mapped_column(String(300), nullable=False)
    display_name: Mapped[str] = mapped_column(String(300), nullable=False)
    provider_family: Mapped[str] = mapped_column(String(120), nullable=False)
    supports_text_input: Mapped[bool] = mapped_column(Boolean, nullable=False)
    supports_image_input: Mapped[bool] = mapped_column(Boolean, nullable=False)
    supports_structured_output: Mapped[bool] = mapped_column(Boolean, nullable=False)
    context_length: Mapped[int | None] = mapped_column(Integer)
    input_price_per_token: Mapped[Decimal | None] = mapped_column(Numeric(24, 16))
    output_price_per_token: Mapped[Decimal | None] = mapped_column(Numeric(24, 16))
    available: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AIAuditEvent(Base):
    __tablename__ = "ai_audit_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[AIAuditAction] = mapped_column(
        Enum(
            AIAuditAction,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_ai_audit_events_action_values",
        ),
        nullable=False,
    )
    task_type: Mapped[AITaskType | None] = mapped_column(
        Enum(
            AITaskType,
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            values_callable=enum_values,
        )
    )
    provider: Mapped[AIProviderName | None] = mapped_column(
        Enum(
            AIProviderName,
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            values_callable=enum_values,
        )
    )
    changed_fields: Mapped[list[str]] = mapped_column(
        JSON, default=list, server_default=text("'[]'::json"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
