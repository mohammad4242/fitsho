from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_mobile_session
from app.auth.service import MobileAccessContext
from app.database.session import get_db

from .schemas import (
    NotificationDeviceResponse,
    NotificationDeviceTokenUpsertRequest,
    NotificationPreferencesResponse,
    NotificationPreferencesUpdateRequest,
)
from .service import (
    NotificationDeviceNotFoundError,
    NotificationProviderMismatchError,
    delete_notification_device,
    get_notification_preferences,
    list_notification_devices,
    register_current_device_token,
    update_notification_preferences,
)

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])
DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentMobileSession = Annotated[MobileAccessContext, Depends(get_current_mobile_session)]


@router.get("/devices", response_model=list[NotificationDeviceResponse])
def read_notification_devices(
    db: DatabaseSession,
    session: CurrentMobileSession,
) -> list[NotificationDeviceResponse]:
    return list_notification_devices(db, session.user.id)


@router.put("/devices/current", response_model=NotificationDeviceResponse)
def upsert_current_notification_device(
    payload: NotificationDeviceTokenUpsertRequest,
    db: DatabaseSession,
    session: CurrentMobileSession,
) -> NotificationDeviceResponse:
    try:
        return register_current_device_token(
            db,
            session,
            provider=payload.provider,
            token_value=payload.token,
        )
    except NotificationProviderMismatchError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Notification provider does not match the device platform",
        ) from None


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_notification_device(
    device_id: UUID,
    db: DatabaseSession,
    session: CurrentMobileSession,
) -> None:
    try:
        delete_notification_device(db, session.user.id, device_id)
    except NotificationDeviceNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification device not found",
        ) from None


@router.get("/preferences", response_model=NotificationPreferencesResponse)
def read_notification_preferences(
    db: DatabaseSession,
    session: CurrentMobileSession,
) -> NotificationPreferencesResponse:
    return get_notification_preferences(db, session.user.id)


@router.put("/preferences", response_model=NotificationPreferencesResponse)
def write_notification_preferences(
    payload: NotificationPreferencesUpdateRequest,
    db: DatabaseSession,
    session: CurrentMobileSession,
) -> NotificationPreferencesResponse:
    return update_notification_preferences(db, session.user.id, payload)
