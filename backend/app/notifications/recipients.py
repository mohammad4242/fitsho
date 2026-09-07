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
    role_values = tuple(roles)
    if not role_values:
        return []
    return list(
        db.scalars(
            select(UserSpecialistRole.user_id)
            .where(UserSpecialistRole.role.in_(role_values))
            .distinct()
        ).all()
    )


def enqueue_specialist_notification(
    db: Session,
    *,
    roles: Iterable[SpecialistRole],
    event_type: str,
    deduplication_key: str,
    data: dict[str, object],
) -> int:
    payload = build_notification_payload(event_type, data=data)
    count = 0
    for user_id in specialist_user_ids(db, roles):
        enqueue_notification_event(
            db,
            user_id=user_id,
            event_type=event_type,
            category="required_reviews",
            deduplication_key=deduplication_key,
            payload=payload,
        )
        count += 1
    return count
