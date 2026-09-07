from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.workout_cycles.enums import WorkoutCycleStatus
from app.workout_cycles.models import WorkoutCycle, WorkoutCycleFeedback, WorkoutCycleWeeklyCheckIn
from app.workout_cycles.service import calculate_current_week, cycle_has_reached_nominal_end

from .content import build_notification_payload
from .models import NotificationOutboxEvent
from .outbox import enqueue_notification_event


@dataclass(frozen=True)
class CycleReminderCandidate:
    cycle_id: UUID
    user_id: UUID
    current_week: int
    has_current_week_check_in: bool
    reached_nominal_end: bool
    has_completion_feedback: bool


@dataclass(frozen=True)
class CycleReminder:
    user_id: UUID
    event_type: str
    category: str
    deduplication_key: str
    payload: dict[str, object]


def due_cycle_reminders(candidate: CycleReminderCandidate) -> tuple[CycleReminder, ...]:
    reminders: list[CycleReminder] = []
    if not candidate.has_current_week_check_in:
        reminders.append(
            CycleReminder(
                user_id=candidate.user_id,
                event_type="weekly_check_in_due",
                category="cycle_reminders",
                deduplication_key=(
                    f"cycle:{candidate.cycle_id}:week:{candidate.current_week}:check-in"
                ),
                payload=build_notification_payload(
                    "weekly_check_in_due",
                    data={
                        "cycle_id": candidate.cycle_id,
                        "week_number": candidate.current_week,
                    },
                ),
            )
        )
    if candidate.reached_nominal_end and not candidate.has_completion_feedback:
        reminders.append(
            CycleReminder(
                user_id=candidate.user_id,
                event_type="cycle_completion_feedback_due",
                category="cycle_reminders",
                deduplication_key=f"cycle:{candidate.cycle_id}:completion-feedback",
                payload=build_notification_payload(
                    "cycle_completion_feedback_due",
                    data={"cycle_id": candidate.cycle_id},
                ),
            )
        )
    return tuple(reminders)


def enqueue_due_cycle_reminders(db: Session, *, now: datetime | None = None) -> int:
    current = now or datetime.now(UTC)
    cycles = db.scalars(
        select(WorkoutCycle).where(WorkoutCycle.status == WorkoutCycleStatus.ACTIVE)
    ).all()
    enqueued = 0
    for cycle in cycles:
        current_week = calculate_current_week(
            cycle.started_at,
            cycle.duration_weeks,
            now=current,
        )
        has_check_in = (
            db.scalar(
                select(WorkoutCycleWeeklyCheckIn.id).where(
                    WorkoutCycleWeeklyCheckIn.cycle_id == cycle.id,
                    WorkoutCycleWeeklyCheckIn.week_number == current_week,
                )
            )
            is not None
        )
        has_feedback = (
            db.scalar(
                select(WorkoutCycleFeedback.id).where(WorkoutCycleFeedback.cycle_id == cycle.id)
            )
            is not None
        )
        candidate = CycleReminderCandidate(
            cycle_id=cycle.id,
            user_id=cycle.user_id,
            current_week=current_week,
            has_current_week_check_in=has_check_in,
            reached_nominal_end=cycle_has_reached_nominal_end(cycle, now=current),
            has_completion_feedback=has_feedback,
        )
        for reminder in due_cycle_reminders(candidate):
            existing = db.scalar(
                select(NotificationOutboxEvent).where(
                    NotificationOutboxEvent.user_id == reminder.user_id,
                    NotificationOutboxEvent.deduplication_key == reminder.deduplication_key,
                )
            )
            if existing is not None:
                continue
            enqueue_notification_event(
                db,
                user_id=reminder.user_id,
                event_type=reminder.event_type,
                category=reminder.category,
                deduplication_key=reminder.deduplication_key,
                payload=reminder.payload,
            )
            enqueued += 1
    db.commit()
    return enqueued
