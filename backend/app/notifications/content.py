from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID


class NotificationContentError(ValueError):
    pass


@dataclass(frozen=True)
class NotificationCopy:
    title: str
    body: str
    channel_id: str
    allowed_data_keys: frozenset[str]


_COPY: dict[str, NotificationCopy] = {
    "workout_plan_approved": NotificationCopy(
        title="برنامه آماده است",
        body="برنامه تمرینی شما برای استفاده آماده شده است.",
        channel_id="fitician-activity",
        allowed_data_keys=frozenset({"plan_id"}),
    ),
    "nutrition_plan_approved": NotificationCopy(
        title="برنامه آماده است",
        body="برنامه شما برای استفاده آماده شده است.",
        channel_id="fitician-activity",
        allowed_data_keys=frozenset({"plan_id"}),
    ),
    "workout_review_required": NotificationCopy(
        title="بررسی برنامه جدید",
        body="یک برنامه جدید برای بررسی شما آماده است.",
        channel_id="fitician-reminders",
        allowed_data_keys=frozenset({"review_id", "plan_id"}),
    ),
    "nutrition_review_required": NotificationCopy(
        title="بررسی برنامه جدید",
        body="یک برنامه جدید برای بررسی شما آماده است.",
        channel_id="fitician-reminders",
        allowed_data_keys=frozenset({"review_id", "plan_id"}),
    ),
    "body_analysis_review_required": NotificationCopy(
        title="بررسی جدید",
        body="یک مورد برای بررسی تخصصی آماده است.",
        channel_id="fitician-health",
        allowed_data_keys=frozenset({"analysis_id", "recipient_role"}),
    ),
    "body_analysis_completed": NotificationCopy(
        title="به‌روزرسانی فیتیچیان",
        body="یک نتیجه جدید در فیتیچیان آماده است.",
        channel_id="fitician-health",
        allowed_data_keys=frozenset({"analysis_id"}),
    ),
    "body_analysis_failed": NotificationCopy(
        title="به‌روزرسانی فیتیچیان",
        body="پردازش درخواست شما کامل نشد؛ دوباره تلاش کنید.",
        channel_id="fitician-health",
        allowed_data_keys=frozenset({"analysis_id"}),
    ),
    "food_photo_analysis_completed": NotificationCopy(
        title="تحلیل غذا آماده است",
        body="نتیجه تحلیل عکس غذا برای بررسی آماده است.",
        channel_id="fitician-nutrition",
        allowed_data_keys=frozenset({"estimate_id"}),
    ),
    "food_photo_analysis_failed": NotificationCopy(
        title="تحلیل غذا کامل نشد",
        body="تحلیل عکس غذا کامل نشد؛ دوباره تلاش کنید.",
        channel_id="fitician-nutrition",
        allowed_data_keys=frozenset({"estimate_id"}),
    ),
    "weekly_check_in_due": NotificationCopy(
        title="یادآوری فیتیچیان",
        body="وقت ثبت گزارش هفتگی شماست.",
        channel_id="fitician-reminders",
        allowed_data_keys=frozenset({"cycle_id", "week_number"}),
    ),
    "cycle_completion_feedback_due": NotificationCopy(
        title="یادآوری فیتیچیان",
        body="چرخه تمرینی شما به پایان رسیده؛ بازخوردتان را ثبت کنید.",
        channel_id="fitician-reminders",
        allowed_data_keys=frozenset({"cycle_id"}),
    ),
    "physician_plan_approved": NotificationCopy(
        title="تصمیم جدید",
        body="یک به‌روزرسانی درباره برنامه شما آماده است.",
        channel_id="fitician-health",
        allowed_data_keys=frozenset({"plan_id", "action"}),
    ),
    "physician_changes_requested": NotificationCopy(
        title="تصمیم جدید",
        body="یک به‌روزرسانی درباره برنامه شما آماده است.",
        channel_id="fitician-health",
        allowed_data_keys=frozenset({"plan_id", "action"}),
    ),
    "physician_plan_rejected": NotificationCopy(
        title="تصمیم جدید",
        body="یک به‌روزرسانی درباره برنامه شما آماده است.",
        channel_id="fitician-health",
        allowed_data_keys=frozenset({"plan_id", "action"}),
    ),
    "physician_labs_requested": NotificationCopy(
        title="اقدام لازم",
        body="برای ادامه بررسی، اطلاعات بیشتری لازم است.",
        channel_id="fitician-health",
        allowed_data_keys=frozenset({"plan_id"}),
    ),
}


PREFERENCE_FIELDS: dict[str, str] = {
    "approved_plans": "approved_plans",
    "required_reviews": "required_reviews",
    "body_analysis": "body_analysis",
    "cycle_reminders": "cycle_reminders",
    "physician_decisions": "physician_decisions",
    "nutrition_updates": "nutrition_updates",
}


def build_notification_payload(
    event_type: str,
    *,
    data: Mapping[str, object] | None = None,
) -> dict[str, object]:
    copy = _COPY.get(event_type)
    if copy is None:
        raise NotificationContentError(f"Unsupported notification event: {event_type}")

    safe_data: dict[str, str] = {"event_type": event_type}
    for key, value in (data or {}).items():
        if key not in copy.allowed_data_keys:
            raise NotificationContentError(f"Unsupported notification data key: {key}")
        if key == "recipient_role" and value not in {"coach", "doctor", "physician"}:
            raise NotificationContentError(f"Unsupported notification recipient role: {value}")
        if isinstance(value, UUID):
            safe_data[key] = str(value)
        elif isinstance(value, (str, int, bool)):
            safe_data[key] = str(value)
        else:
            raise NotificationContentError(f"Unsupported notification data value: {key}")
    return {
        "title": copy.title,
        "body": copy.body,
        "channel_id": copy.channel_id,
        "data": safe_data,
    }
