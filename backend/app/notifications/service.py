from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.auth.service import MobileAccessContext

from .models import NotificationDevice, NotificationDeviceToken, NotificationPreference
from .schemas import (
    NotificationDeviceResponse,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdateRequest,
)


class NotificationDeviceNotFoundError(Exception):
    pass


def _device_response(device: NotificationDevice) -> NotificationDeviceResponse:
    return NotificationDeviceResponse(
        id=device.id,
        device_id=device.device_id,
        platform=device.platform,
        app_version=device.app_version,
        device_name=device.device_name,
        has_active_token=any(token.invalid_at is None for token in device.tokens),
        created_at=device.created_at,
        updated_at=device.updated_at,
        last_seen_at=device.last_seen_at,
    )


def register_current_device_token(
    db: Session,
    context: MobileAccessContext,
    *,
    provider: str,
    token_value: str,
) -> NotificationDeviceResponse:
    now = datetime.now(UTC)
    family = context.family
    device = db.scalar(
        select(NotificationDevice)
        .where(
            NotificationDevice.user_id == context.user.id,
            NotificationDevice.device_id == family.device_id,
        )
        .with_for_update()
    )
    if device is None:
        device = NotificationDevice(
            user_id=context.user.id,
            device_id=family.device_id,
            platform=family.platform,
            app_version=family.app_version,
            device_name=family.device_name,
            created_at=now,
            updated_at=now,
            last_seen_at=now,
        )
        db.add(device)
        db.flush()
    else:
        device.platform = family.platform
        device.app_version = family.app_version
        device.device_name = family.device_name
        device.updated_at = now
        device.last_seen_at = now

    token_hash = sha256(token_value.encode("utf-8")).hexdigest()
    token = db.scalar(
        select(NotificationDeviceToken)
        .where(
            NotificationDeviceToken.provider == provider,
            NotificationDeviceToken.token_hash == token_hash,
        )
        .with_for_update()
    )
    if token is not None and token.device_id != device.id:
        token.device_id = device.id
    db.execute(
        update(NotificationDeviceToken)
        .where(
            NotificationDeviceToken.device_id == device.id,
            NotificationDeviceToken.provider == provider,
            NotificationDeviceToken.token_hash != token_hash,
            NotificationDeviceToken.invalid_at.is_(None),
        )
        .values(invalid_at=now, invalid_reason="replaced", updated_at=now)
    )
    if token is None:
        token = NotificationDeviceToken(
            device_id=device.id,
            provider=provider,
            token_hash=token_hash,
            token_value=token_value,
            created_at=now,
            updated_at=now,
            last_seen_at=now,
        )
        db.add(token)
    else:
        token.token_value = token_value
        token.invalid_at = None
        token.invalid_reason = None
        token.updated_at = now
        token.last_seen_at = now
    db.commit()
    db.refresh(device)
    list(device.tokens)
    return _device_response(device)


def list_notification_devices(db: Session, user_id: UUID) -> list[NotificationDeviceResponse]:
    devices = db.scalars(
        select(NotificationDevice)
        .where(NotificationDevice.user_id == user_id)
        .options(selectinload(NotificationDevice.tokens))
        .order_by(NotificationDevice.created_at)
    ).all()
    return [_device_response(device) for device in devices]


def delete_notification_device(db: Session, user_id: UUID, device_id: UUID) -> None:
    device = db.scalar(
        select(NotificationDevice).where(
            NotificationDevice.id == device_id,
            NotificationDevice.user_id == user_id,
        )
    )
    if device is None:
        raise NotificationDeviceNotFoundError
    db.delete(device)
    db.commit()


def _preferences_response(
    preferences: NotificationPreference | None,
) -> NotificationPreferencesResponse:
    if preferences is None:
        return NotificationPreferencesResponse(
            enabled=True,
            approved_plans=True,
            required_reviews=True,
            body_analysis=True,
            cycle_reminders=True,
            physician_decisions=True,
            nutrition_updates=True,
            updated_at=None,
        )
    return NotificationPreferencesResponse(
        enabled=preferences.enabled,
        approved_plans=preferences.approved_plans,
        required_reviews=preferences.required_reviews,
        body_analysis=preferences.body_analysis,
        cycle_reminders=preferences.cycle_reminders,
        physician_decisions=preferences.physician_decisions,
        nutrition_updates=preferences.nutrition_updates,
        updated_at=preferences.updated_at,
    )


def get_notification_preferences(
    db: Session,
    user_id: UUID,
) -> NotificationPreferencesResponse:
    return _preferences_response(db.get(NotificationPreference, user_id))


def update_notification_preferences(
    db: Session,
    user_id: UUID,
    payload: NotificationPreferencesUpdateRequest,
) -> NotificationPreferencesResponse:
    now = datetime.now(UTC)
    preferences = db.get(NotificationPreference, user_id, with_for_update=True)
    if preferences is None:
        preferences = NotificationPreference(user_id=user_id, created_at=now)
        db.add(preferences)
    preferences.enabled = payload.enabled
    preferences.approved_plans = payload.approved_plans
    preferences.required_reviews = payload.required_reviews
    preferences.body_analysis = payload.body_analysis
    preferences.cycle_reminders = payload.cycle_reminders
    preferences.physician_decisions = payload.physician_decisions
    preferences.nutrition_updates = payload.nutrition_updates
    preferences.updated_at = now
    db.commit()
    db.refresh(preferences)
    return _preferences_response(preferences)
