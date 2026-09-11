from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.notifications.models import (
    NotificationDevice,
    NotificationDeviceToken,
    NotificationEventDelivery,
    NotificationOutboxEvent,
)
from app.notifications.outbox import enqueue_notification_event
from app.notifications.worker import claim_outbox_events, run_outbox_once


def _user(db: Session) -> User:
    user = User(email=f"outbox-{uuid4()}@example.com", password_hash="test-hash")
    db.add(user)
    db.commit()
    return user


def test_domain_event_and_outbox_share_the_same_transaction(db: Session) -> None:
    user = _user(db)

    event = enqueue_notification_event(
        db,
        user_id=user.id,
        event_type="plan_approved",
        category="approved_plans",
        deduplication_key="plan:1:approved",
        payload={"plan_id": "plan-1"},
    )
    db.flush()
    assert db.get(NotificationOutboxEvent, event.id) is not None
    db.rollback()

    assert db.get(NotificationOutboxEvent, event.id) is None


def test_outbox_worker_fans_out_once_and_deduplicates_deliveries(db: Session) -> None:
    user = _user(db)
    device = NotificationDevice(
        user_id=user.id,
        device_id="device-1",
        platform="android",
        app_version="1.0.0",
    )
    db.add(device)
    db.flush()
    db.add(
        NotificationDeviceToken(
            device_id=device.id,
            provider="fcm",
            token_hash=sha256(b"token").hexdigest(),
            token_value="token",
        )
    )
    enqueue_notification_event(
        db,
        user_id=user.id,
        event_type="body_analysis_completed",
        category="body_analysis",
        deduplication_key="analysis:1:completed",
        payload={"analysis_id": "analysis-1"},
    )
    db.commit()

    now = datetime.now(UTC)
    assert run_outbox_once(db, worker_id="worker-1", now=now) == 1
    assert run_outbox_once(db, worker_id="worker-2", now=now + timedelta(seconds=1)) == 0

    event = db.scalar(
        select(NotificationOutboxEvent).where(NotificationOutboxEvent.user_id == user.id)
    )
    assert event is not None
    assert event.status == "processed"
    deliveries = db.scalars(
        select(NotificationEventDelivery).where(NotificationEventDelivery.event_id == event.id)
    ).all()
    assert len(deliveries) == 1
    assert deliveries[0].status == "pending"


def test_outbox_worker_fans_out_both_fcm_and_apns_tokens(db: Session) -> None:
    user = _user(db)
    android = NotificationDevice(
        user_id=user.id,
        device_id="android-device",
        platform="android",
        app_version="1.0.0",
    )
    ios = NotificationDevice(
        user_id=user.id,
        device_id="ios-device",
        platform="ios",
        app_version="1.0.0",
    )
    db.add_all([android, ios])
    db.flush()
    db.add_all(
        [
            NotificationDeviceToken(
                device_id=android.id,
                provider="fcm",
                token_hash=sha256(b"fcm-token").hexdigest(),
                token_value="fcm-token",
            ),
            NotificationDeviceToken(
                device_id=ios.id,
                provider="apns",
                token_hash=sha256(b"apns-token").hexdigest(),
                token_value="apns-token",
            ),
        ]
    )
    enqueue_notification_event(
        db,
        user_id=user.id,
        event_type="body_analysis_completed",
        category="body_analysis",
        deduplication_key="analysis:both-platforms",
        payload={"analysis_id": "analysis-1"},
    )
    db.commit()

    assert run_outbox_once(db, worker_id="worker-both") == 1
    assert len(db.scalars(select(NotificationEventDelivery)).all()) == 2


def test_stale_outbox_lease_can_be_reclaimed(db: Session) -> None:
    user = _user(db)
    event = enqueue_notification_event(
        db,
        user_id=user.id,
        event_type="required_review",
        category="required_reviews",
        deduplication_key="review:1:required",
        payload={"review_id": "review-1"},
    )
    db.commit()
    first_now = datetime.now(UTC)
    first_claim = claim_outbox_events(
        db,
        worker_id="worker-1",
        now=first_now,
        lease_seconds=30,
        batch_size=1,
    )
    assert first_claim == [event.id]

    reclaimed = claim_outbox_events(
        db,
        worker_id="worker-2",
        now=first_now + timedelta(minutes=1),
        lease_seconds=30,
        batch_size=1,
    )

    assert reclaimed == [event.id]
    assert db.get(NotificationOutboxEvent, event.id).locked_by == "worker-2"
