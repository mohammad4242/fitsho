from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import NotificationOutboxEvent


def enqueue_notification_event(
    db: Session,
    *,
    user_id: UUID,
    event_type: str,
    category: str,
    deduplication_key: str,
    payload: dict[str, object],
    available_at: datetime | None = None,
) -> NotificationOutboxEvent:
    existing = db.scalar(
        select(NotificationOutboxEvent).where(
            NotificationOutboxEvent.user_id == user_id,
            NotificationOutboxEvent.deduplication_key == deduplication_key,
        )
    )
    if existing is not None:
        return existing
    event = NotificationOutboxEvent(
        user_id=user_id,
        event_type=event_type,
        category=category,
        deduplication_key=deduplication_key,
        payload=payload,
        available_at=available_at or datetime.now(UTC),
    )
    db.add(event)
    db.flush()
    return event
