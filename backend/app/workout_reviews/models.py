from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.workout_reviews.enums import WorkoutReviewStatus

if TYPE_CHECKING:
    from app.workouts.models import WorkoutPlan


def enum_values(members: type[StrEnum]) -> list[str]:
    return [member.value for member in members]


class WorkoutPlanReview(Base):
    __tablename__ = "workout_plan_reviews"
    __table_args__ = (
        UniqueConstraint("source_plan_id", name="uq_workout_plan_reviews_source_plan_id"),
        UniqueConstraint("approved_plan_id", name="uq_workout_plan_reviews_approved_plan_id"),
        CheckConstraint(
            "draft_revision > 0",
            name="ck_workout_plan_reviews_draft_revision_positive",
        ),
        CheckConstraint(
            "coach_note IS NULL OR char_length(coach_note) <= 2000",
            name="ck_workout_plan_reviews_coach_note_length",
        ),
        CheckConstraint(
            "(claimed_by_user_id IS NULL AND lease_acquired_at IS NULL "
            "AND lease_expires_at IS NULL) OR "
            "(claimed_by_user_id IS NOT NULL AND lease_acquired_at IS NOT NULL "
            "AND lease_expires_at IS NOT NULL)",
            name="ck_workout_plan_reviews_lease_fields_consistent",
        ),
        CheckConstraint(
            "lease_expires_at IS NULL OR lease_expires_at > lease_acquired_at",
            name="ck_workout_plan_reviews_lease_range",
        ),
        Index("ix_workout_plan_reviews_status", "status"),
        Index("ix_workout_plan_reviews_user_id", "user_id"),
        Index("ix_workout_plan_reviews_claimed_by_user_id", "claimed_by_user_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("workout_plans.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[WorkoutReviewStatus] = mapped_column(
        Enum(
            WorkoutReviewStatus,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=enum_values,
            name="ck_workout_plan_reviews_status_values",
        ),
        default=WorkoutReviewStatus.PENDING,
        server_default=WorkoutReviewStatus.PENDING.value,
        nullable=False,
    )
    claimed_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    lease_acquired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    coach_note: Mapped[str | None] = mapped_column(String(2000))
    draft_payload: Mapped[dict[str, object] | None] = mapped_column(JSON)
    draft_revision: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    approved_plan_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workout_plans.id", ondelete="SET NULL")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    source_plan: Mapped[WorkoutPlan] = relationship(
        foreign_keys=[source_plan_id], back_populates="source_review"
    )
    approved_plan: Mapped[WorkoutPlan | None] = relationship(
        foreign_keys=[approved_plan_id], back_populates="approval_review"
    )
