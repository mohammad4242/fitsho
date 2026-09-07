from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class AccountDeletionStatus(StrEnum):
    PENDING = "pending"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class AccountDeletionRequest(Base):
    """Minimal lifecycle record retained after the account itself is deleted."""

    __tablename__ = "account_deletion_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'cancelled', 'completed')",
            name="ck_account_deletion_requests_status",
        ),
        Index(
            "ix_account_deletion_requests_user_id_requested_at",
            "user_id",
            "requested_at",
        ),
        Index(
            "ix_account_deletion_requests_pending_grace_period",
            "status",
            "grace_period_ends_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[AccountDeletionStatus] = mapped_column(
        Enum(
            AccountDeletionStatus,
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            values_callable=lambda members: [member.value for member in members],
        ),
        default=AccountDeletionStatus.PENDING,
        server_default=AccountDeletionStatus.PENDING.value,
        nullable=False,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reauthenticated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    grace_period_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
