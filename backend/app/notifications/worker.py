from __future__ import annotations

import logging
import socket
import time
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import Table, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.session import get_engine

from .models import (
    NotificationDevice,
    NotificationDeviceToken,
    NotificationEventDelivery,
    NotificationOutboxEvent,
)

logger = logging.getLogger(__name__)


def claim_outbox_events(
    db: Session,
    *,
    worker_id: str,
    now: datetime,
    lease_seconds: int,
    batch_size: int,
) -> list[UUID]:
    stale_before = now - timedelta(seconds=lease_seconds)
    events = db.scalars(
        select(NotificationOutboxEvent)
        .where(
            or_(
                (
                    (NotificationOutboxEvent.status == "pending")
                    & (NotificationOutboxEvent.available_at <= now)
                ),
                (
                    (NotificationOutboxEvent.status == "processing")
                    & (NotificationOutboxEvent.locked_at <= stale_before)
                ),
            )
        )
        .order_by(NotificationOutboxEvent.created_at)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    ).all()
    for event in events:
        event.status = "processing"
        event.locked_at = now
        event.locked_by = worker_id
    if not events:
        db.rollback()
        return []
    db.commit()
    return [event.id for event in events]


def process_outbox_event(
    db: Session,
    event_id: UUID,
    *,
    worker_id: str,
    now: datetime,
) -> bool:
    event = db.scalar(
        select(NotificationOutboxEvent)
        .where(
            NotificationOutboxEvent.id == event_id,
            NotificationOutboxEvent.status == "processing",
            NotificationOutboxEvent.locked_by == worker_id,
        )
        .with_for_update()
    )
    if event is None:
        db.rollback()
        return False

    token_ids = db.scalars(
        select(NotificationDeviceToken.id)
        .join(NotificationDevice, NotificationDevice.id == NotificationDeviceToken.device_id)
        .where(
            NotificationDevice.user_id == event.user_id,
            NotificationDeviceToken.provider == "fcm",
            NotificationDeviceToken.invalid_at.is_(None),
        )
    ).all()
    delivery_table = cast(Table, NotificationEventDelivery.__table__)
    for token_id in token_ids:
        db.execute(
            insert(delivery_table)
            .values(
                id=uuid4(),
                event_id=event.id,
                token_id=token_id,
                status="pending",
                created_at=now,
                attempt_count=0,
            )
            .on_conflict_do_nothing(index_elements=["event_id", "token_id"])
        )
    event.status = "processed"
    event.processed_at = now
    event.locked_at = None
    event.locked_by = None
    db.commit()
    return True


def run_outbox_once(
    db: Session,
    *,
    worker_id: str,
    now: datetime | None = None,
    lease_seconds: int = 60,
    batch_size: int = 100,
) -> int:
    current = now or datetime.now(UTC)
    event_ids = claim_outbox_events(
        db,
        worker_id=worker_id,
        now=current,
        lease_seconds=lease_seconds,
        batch_size=batch_size,
    )
    processed = 0
    for event_id in event_ids:
        try:
            processed += int(
                process_outbox_event(
                    db,
                    event_id,
                    worker_id=worker_id,
                    now=current,
                )
            )
        except Exception:
            db.rollback()
            logger.exception("Notification outbox event processing failed")
    return processed


def _worker_id() -> str:
    return f"{socket.gethostname()}:{uuid4()}"


def run_worker(settings: Settings) -> None:
    worker_id = _worker_id()
    engine = get_engine(settings.database_url)
    while True:
        try:
            with Session(engine) as db:
                run_outbox_once(
                    db,
                    worker_id=worker_id,
                    lease_seconds=settings.notification_worker_lease_seconds,
                    batch_size=settings.notification_worker_batch_size,
                )
        except Exception:
            logger.exception("Notification worker iteration failed")
        time.sleep(settings.notification_worker_poll_seconds)


if __name__ == "__main__":
    run_worker(get_settings())
