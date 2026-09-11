from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.body_analysis.enums import SpecialistRole
from app.body_analysis.models import UserSpecialistRole
from app.notifications.content import NotificationContentError, build_notification_payload
from app.notifications.models import (
    NotificationDevice,
    NotificationDeviceToken,
    NotificationEventDelivery,
    NotificationOutboxEvent,
    NotificationPreference,
)
from app.notifications.outbox import enqueue_notification_event
from app.notifications.recipients import enqueue_specialist_notification
from app.notifications.reminders import (
    CycleReminderCandidate,
    due_cycle_reminders,
)
from app.notifications.worker import run_outbox_once
from app.workout_reviews.repository import ensure_pending_review
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutPlan


def test_notification_copy_is_static_and_rejects_sensitive_payload_keys() -> None:
    payload = build_notification_payload(
        "body_analysis_completed",
        data={"analysis_id": uuid4()},
    )

    assert payload["title"] == "به‌روزرسانی فیتیچیان"
    assert payload["body"] == "یک نتیجه جدید در فیتیچیان آماده است."
    assert payload["channel_id"] == "fitician-health"
    assert "medical" not in str(payload).lower()

    with pytest.raises(NotificationContentError):
        build_notification_payload(
            "body_analysis_completed",
            data={"notes": "private medical note"},
        )

    with pytest.raises(NotificationContentError):
        build_notification_payload(
            "body_analysis_review_required",
            data={"analysis_id": uuid4(), "recipient_role": "admin"},
        )

    food_payload = build_notification_payload(
        "food_photo_analysis_completed",
        data={"estimate_id": uuid4()},
    )
    assert food_payload["channel_id"] == "fitician-nutrition"
    assert set(food_payload["data"]) == {"event_type", "estimate_id"}


def test_body_analysis_review_notifications_preserve_the_authorized_specialist_role(
    db: Session,
) -> None:
    coach = User(email=f"role-coach-{uuid4()}@example.com", password_hash="test-hash")
    doctor = User(email=f"role-doctor-{uuid4()}@example.com", password_hash="test-hash")
    db.add_all([coach, doctor])
    db.flush()
    db.add_all(
        [
            UserSpecialistRole(user_id=coach.id, role=SpecialistRole.COACH),
            UserSpecialistRole(user_id=doctor.id, role=SpecialistRole.DOCTOR),
        ]
    )

    enqueue_specialist_notification(
        db,
        roles=(SpecialistRole.COACH, SpecialistRole.DOCTOR),
        event_type="body_analysis_review_required",
        deduplication_key="body-analysis:role-routing",
        data={"analysis_id": uuid4()},
    )
    db.commit()

    events = db.scalars(
        select(NotificationOutboxEvent).where(
            NotificationOutboxEvent.event_type == "body_analysis_review_required"
        )
    ).all()
    assert {
        event.user_id: event.payload["data"]["recipient_role"]
        for event in events
    } == {
        coach.id: "coach",
        doctor.id: "doctor",
    }


def test_cycle_reminders_are_due_only_once_per_missing_action() -> None:
    cycle_id = uuid4()
    user_id = uuid4()
    reminders = due_cycle_reminders(
        CycleReminderCandidate(
            cycle_id=cycle_id,
            user_id=user_id,
            current_week=2,
            has_current_week_check_in=False,
            reached_nominal_end=True,
            has_completion_feedback=False,
        )
    )

    assert [(item.event_type, item.deduplication_key) for item in reminders] == [
        ("weekly_check_in_due", f"cycle:{cycle_id}:week:2:check-in"),
        ("cycle_completion_feedback_due", f"cycle:{cycle_id}:completion-feedback"),
    ]
    assert all(item.user_id == user_id for item in reminders)


def test_disabled_notification_category_is_processed_without_delivery(db: Session) -> None:
    user = User(email=f"notifications-{uuid4()}@example.com", password_hash="test-hash")
    db.add(user)
    db.flush()
    device = NotificationDevice(
        user_id=user.id,
        device_id="notification-device",
        platform="android",
        app_version="1.0.0",
    )
    db.add(device)
    db.flush()
    db.add(
        NotificationDeviceToken(
            device_id=device.id,
            provider="fcm",
            token_hash=sha256(b"notification-token").hexdigest(),
            token_value="notification-token",
        )
    )
    db.add(NotificationPreference(user_id=user.id, approved_plans=False))
    event = enqueue_notification_event(
        db,
        user_id=user.id,
        event_type="workout_plan_approved",
        category="approved_plans",
        deduplication_key="workout-plan:approved",
        payload=build_notification_payload(
            "workout_plan_approved",
            data={"plan_id": uuid4()},
        ),
    )
    db.commit()

    assert run_outbox_once(db, worker_id="preference-worker") == 1

    db.refresh(event)
    assert event.status == "processed"
    assert db.scalars(select(NotificationEventDelivery)).all() == []


def test_workout_review_event_targets_explicit_coaches(db: Session) -> None:
    member = User(email=f"member-{uuid4()}@example.com", password_hash="test-hash")
    coach = User(email=f"coach-{uuid4()}@example.com", password_hash="test-hash")
    db.add_all([member, coach])
    db.flush()
    db.add(UserSpecialistRole(user_id=coach.id, role=SpecialistRole.COACH))
    plan = WorkoutPlan(
        user_id=member.id,
        status=WorkoutPlanStatus.PENDING_REVIEW,
        generation_signature="a" * 64,
        profile_snapshot={"plan_duration_weeks": 4},
        provider="fake",
        model_id="fake-model",
        prompt_version="v1",
        generation_policy_version="v1",
        candidate_set_hash="b" * 64,
        generation_method="ai",
    )
    db.add(plan)
    db.flush()

    review = ensure_pending_review(db, plan)
    db.commit()

    event = db.scalar(
        select(NotificationOutboxEvent).where(NotificationOutboxEvent.user_id == coach.id)
    )
    assert event is not None
    assert event.event_type == "workout_review_required"
    assert event.payload["data"] == {
        "event_type": "workout_review_required",
        "review_id": str(review.id),
        "plan_id": str(plan.id),
    }


def test_cycle_reminder_producer_persists_and_deduplicates_events(db: Session) -> None:
    from app.notifications.reminders import enqueue_due_cycle_reminders
    from app.workout_cycles.models import WorkoutCycle

    now = datetime(2026, 9, 8, 12, tzinfo=UTC)
    user = User(email=f"cycle-{uuid4()}@example.com", password_hash="test-hash")
    db.add(user)
    db.flush()
    plan = WorkoutPlan(
        user_id=user.id,
        status=WorkoutPlanStatus.ACTIVE,
        generation_signature="c" * 64,
        profile_snapshot={"plan_duration_weeks": 4},
        provider="fake",
        model_id="fake-model",
        prompt_version="v1",
        generation_policy_version="v1",
        candidate_set_hash="d" * 64,
        generation_method="ai",
    )
    db.add(plan)
    db.flush()
    db.add(
        WorkoutCycle(
            user_id=user.id,
            workout_plan_id=plan.id,
            duration_weeks=4,
            started_at=now - timedelta(days=29),
        )
    )
    db.flush()

    enqueued = enqueue_due_cycle_reminders(db, now=now)
    assert enqueued >= 2
    assert enqueue_due_cycle_reminders(db, now=now) == 0
    events = db.scalars(
        select(NotificationOutboxEvent).where(NotificationOutboxEvent.user_id == user.id)
    ).all()
    assert len(events) == 2


def test_reminder_payload_has_no_member_or_medical_text() -> None:
    reminder = due_cycle_reminders(
        CycleReminderCandidate(
            cycle_id=uuid4(),
            user_id=uuid4(),
            current_week=1,
            has_current_week_check_in=False,
            reached_nominal_end=False,
            has_completion_feedback=False,
        )
    )[0]

    assert reminder.payload["body"] == "وقت ثبت گزارش هفتگی شماست."
    assert "note" not in str(reminder.payload).lower()
