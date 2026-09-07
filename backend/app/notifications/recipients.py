from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.body_analysis.enums import SpecialistRole
from app.body_analysis.models import UserSpecialistRole

from .content import build_notification_payload
from .outbox import enqueue_notification_event


def specialist_user_ids(db: Session, roles: Iterable[SpecialistRole]) -> list[UUID]:
    return [user_id for user_id, _role in specialist_user_roles(db, roles)]


def specialist_user_roles(
    db: Session,
    roles: Iterable[SpecialistRole],
) -> list[tuple[UUID, SpecialistRole]]:
    role_values = tuple(dict.fromkeys(roles))
    if not role_values:
        return []
    priority = {role: index for index, role in enumerate(role_values)}
    rows = db.execute(
        select(UserSpecialistRole.user_id, UserSpecialistRole.role).where(
            UserSpecialistRole.role.in_(role_values)
        )
    ).all()
    selected: dict[UUID, SpecialistRole] = {}
    for user_id, role in rows:
        if user_id not in selected or priority[role] < priority[selected[user_id]]:
            selected[user_id] = role
    return sorted(selected.items(), key=lambda item: str(item[0]))


def enqueue_specialist_notification(
    db: Session,
    *,
    roles: Iterable[SpecialistRole],
    event_type: str,
    deduplication_key: str,
    data: dict[str, object],
) -> int:
    count = 0
    for user_id, role in specialist_user_roles(db, roles):
        notification_data = data
        if event_type == "body_analysis_review_required":
            notification_data = {**data, "recipient_role": role.value}
        enqueue_notification_event(
            db,
            user_id=user_id,
            event_type=event_type,
            category="required_reviews",
            deduplication_key=deduplication_key,
            payload=build_notification_payload(event_type, data=notification_data),
        )
        count += 1
    return count
