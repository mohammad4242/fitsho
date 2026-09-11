from __future__ import annotations

import logging
import socket
import time
from collections.abc import Collection, Mapping
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import Table, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.database.session import get_engine

from .apns import ApnsConfigurationError, build_apns_provider
from .content import PREFERENCE_FIELDS
from .fcm import FcmConfigurationError, build_fcm_provider
from .models import (
    NotificationDevice,
    NotificationDeviceToken,
    NotificationEventDelivery,
    NotificationOutboxEvent,
    NotificationPreference,
)
from .provider import NotificationProvider, NotificationProviderName, NotificationSendOutcome
from .reminders import enqueue_due_cycle_reminders

logger = logging.getLogger(__name__)

NotificationProviders = NotificationProvider | Mapping[
    NotificationProviderName,
    NotificationProvider,
]


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

    preference = db.get(NotificationPreference, event.user_id)
    preference_field = PREFERENCE_FIELDS.get(event.category)
    if preference_field is None:
        logger.error("Unsupported notification preference category: %s", event.category)
    elif preference is not None and (
        not preference.enabled or not bool(getattr(preference, preference_field))
    ):
        event.status = "processed"
        event.processed_at = now
        event.locked_at = None
        event.locked_by = None
        db.commit()
        return True

    token_ids = db.scalars(
        select(NotificationDeviceToken.id)
        .join(NotificationDevice, NotificationDevice.id == NotificationDeviceToken.device_id)
        .where(
            NotificationDevice.user_id == event.user_id,
            NotificationDeviceToken.provider.in_(("fcm", "apns")),
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


def claim_notification_deliveries(
    db: Session,
    *,
    worker_id: str,
    now: datetime,
    lease_seconds: int,
    batch_size: int,
    provider_names: Collection[str] | None = None,
) -> list[UUID]:
    stale_before = now - timedelta(seconds=lease_seconds)
    token_conditions = [NotificationDeviceToken.invalid_at.is_(None)]
    if provider_names is not None:
        token_conditions.append(NotificationDeviceToken.provider.in_(provider_names))
    deliveries = db.scalars(
        select(NotificationEventDelivery)
        .join(
            NotificationDeviceToken,
            NotificationDeviceToken.id == NotificationEventDelivery.token_id,
        )
        .where(
            *token_conditions,
            or_(
                (
                    (NotificationEventDelivery.status == "pending")
                    & (NotificationEventDelivery.next_attempt_at <= now)
                ),
                (
                    (NotificationEventDelivery.status == "processing")
                    & (NotificationEventDelivery.locked_at <= stale_before)
                ),
            ),
        )
        .order_by(NotificationEventDelivery.created_at)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    ).all()
    for delivery in deliveries:
        delivery.status = "processing"
        delivery.locked_at = now
        delivery.locked_by = worker_id
    if not deliveries:
        db.rollback()
        return []
    db.commit()
    return [delivery.id for delivery in deliveries]


def process_notification_delivery(
    db: Session,
    delivery_id: UUID,
    *,
    provider: NotificationProviders,
    worker_id: str,
    now: datetime,
    max_attempts: int,
    retry_base_seconds: int,
    retry_max_seconds: int,
) -> bool:
    delivery = db.scalar(
        select(NotificationEventDelivery)
        .where(
            NotificationEventDelivery.id == delivery_id,
            NotificationEventDelivery.status == "processing",
            NotificationEventDelivery.locked_by == worker_id,
        )
        .with_for_update()
    )
    if delivery is None:
        db.rollback()
        return False
    event = db.get(NotificationOutboxEvent, delivery.event_id)
    token = db.get(NotificationDeviceToken, delivery.token_id)
    if event is None or token is None or token.invalid_at is not None:
        delivery.status = "dead_letter"
        delivery.dead_letter_at = now
        delivery.last_error = "TOKEN_UNAVAILABLE"
        delivery.locked_at = None
        delivery.locked_by = None
        db.commit()
        return True

    selected_provider = _provider_for_token(provider, token.provider)
    if selected_provider is None:
        delivery.status = "pending"
        delivery.locked_at = None
        delivery.locked_by = None
        delivery.last_error = "PROVIDER_UNAVAILABLE"
        db.commit()
        return True

    delivery.attempt_count += 1
    try:
        outcome = selected_provider.send(
            token_value=token.token_value,
            event_type=event.event_type,
            payload=event.payload,
        )
    except Exception:
        logger.exception("Notification provider delivery failed")
        outcome = NotificationSendOutcome.retryable("PROVIDER_EXCEPTION")

    delivery.locked_at = None
    delivery.locked_by = None
    if outcome.kind == "sent":
        delivery.status = "sent"
        delivery.sent_at = now
        delivery.provider_message_id = outcome.provider_message_id
        delivery.last_error = None
    elif outcome.kind == "invalid_token":
        token.invalid_at = now
        token.invalid_reason = outcome.error_code or "INVALID_TOKEN"
        delivery.status = "dead_letter"
        delivery.dead_letter_at = now
        delivery.last_error = outcome.error_code or "INVALID_TOKEN"
    elif outcome.kind == "permanent" or delivery.attempt_count >= max(1, max_attempts):
        delivery.status = "dead_letter"
        delivery.dead_letter_at = now
        delivery.last_error = outcome.error_code or "PROVIDER_ERROR"
    else:
        delay = min(
            retry_max_seconds,
            retry_base_seconds * 2 ** max(delivery.attempt_count - 1, 0),
        )
        delivery.status = "pending"
        delivery.next_attempt_at = now + timedelta(seconds=delay)
        delivery.last_error = outcome.error_code or "PROVIDER_ERROR"
    db.commit()
    return True


def run_delivery_once(
    db: Session,
    *,
    provider: NotificationProviders,
    worker_id: str,
    now: datetime | None = None,
    lease_seconds: int = 60,
    batch_size: int = 100,
    max_attempts: int = 5,
    retry_base_seconds: int = 30,
    retry_max_seconds: int = 1800,
) -> int:
    provider_names = tuple(provider.keys()) if isinstance(provider, Mapping) else ("fcm",)
    if not provider_names:
        return 0
    current = now or datetime.now(UTC)
    delivery_ids = claim_notification_deliveries(
        db,
        worker_id=worker_id,
        now=current,
        lease_seconds=lease_seconds,
        batch_size=batch_size,
        provider_names=provider_names,
    )
    processed = 0
    for delivery_id in delivery_ids:
        try:
            processed += int(
                process_notification_delivery(
                    db,
                    delivery_id,
                    provider=provider,
                    worker_id=worker_id,
                    now=current,
                    max_attempts=max_attempts,
                    retry_base_seconds=retry_base_seconds,
                    retry_max_seconds=retry_max_seconds,
                )
            )
        except Exception:
            db.rollback()
            logger.exception("Notification delivery processing failed")
    return processed


def run_notification_once(
    db: Session,
    *,
    worker_id: str,
    provider: NotificationProviders | None,
    now: datetime | None = None,
    lease_seconds: int = 60,
    batch_size: int = 100,
    max_attempts: int = 5,
    retry_base_seconds: int = 30,
    retry_max_seconds: int = 1800,
) -> int:
    current = now or datetime.now(UTC)
    reminders = enqueue_due_cycle_reminders(db, now=current)
    processed = run_outbox_once(
        db,
        worker_id=worker_id,
        now=current,
        lease_seconds=lease_seconds,
        batch_size=batch_size,
    )
    if provider is not None:
        processed += run_delivery_once(
            db,
            provider=provider,
            worker_id=worker_id,
            now=current,
            lease_seconds=lease_seconds,
            batch_size=batch_size,
            max_attempts=max_attempts,
            retry_base_seconds=retry_base_seconds,
            retry_max_seconds=retry_max_seconds,
        )
    return processed + reminders


def _worker_id() -> str:
    return f"{socket.gethostname()}:{uuid4()}"


def _provider_for_token(
    provider: NotificationProviders,
    provider_name: str,
) -> NotificationProvider | None:
    if isinstance(provider, Mapping):
        if provider_name not in {"fcm", "apns"}:
            return None
        return provider.get(cast(NotificationProviderName, provider_name))
    return provider if provider_name == "fcm" else None


def _close_provider(provider: NotificationProvider) -> None:
    close = getattr(provider, "close", None)
    if callable(close):
        close()


def run_worker(settings: Settings) -> None:
    worker_id = _worker_id()
    engine = get_engine(settings.database_url)
    providers: dict[NotificationProviderName, NotificationProvider] = {}
    try:
        try:
            fcm_provider = build_fcm_provider(settings)
            if fcm_provider is not None:
                providers["fcm"] = fcm_provider
        except FcmConfigurationError:
            logger.exception("FCM provider configuration is invalid")
        try:
            apns_provider = build_apns_provider(settings)
            if apns_provider is not None:
                providers["apns"] = apns_provider
        except ApnsConfigurationError:
            logger.exception("APNs provider configuration is invalid")
        while True:
            try:
                with Session(engine) as db:
                    run_notification_once(
                        db,
                        worker_id=worker_id,
                        provider=providers or None,
                        lease_seconds=settings.notification_worker_lease_seconds,
                        batch_size=settings.notification_worker_batch_size,
                        max_attempts=settings.notification_max_delivery_attempts,
                        retry_base_seconds=settings.notification_retry_base_seconds,
                        retry_max_seconds=settings.notification_retry_max_seconds,
                    )
            except Exception:
                logger.exception("Notification worker iteration failed")
            time.sleep(settings.notification_worker_poll_seconds)
    finally:
        for provider in providers.values():
            _close_provider(provider)


if __name__ == "__main__":
    run_worker(get_settings())
