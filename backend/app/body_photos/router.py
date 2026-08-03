from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.cookies import require_trusted_origin
from app.auth.dependencies import get_current_user
from app.auth.models import User
from app.body_photos.enums import BodyPhotoConsentType, BodyPhotoView
from app.body_photos.image_validation import BodyPhotoValidationError
from app.body_photos.models import BodyPhotoConsent, BodyPhotoSession
from app.body_photos.schemas import (
    BodyPhotoConsentInput,
    BodyPhotoConsentResponse,
    BodyPhotoResponse,
    BodyPhotoSessionCreate,
    BodyPhotoSessionListResponse,
    BodyPhotoSessionResponse,
    BodyPhotoSubmit,
)
from app.body_photos.service import (
    BodyPhotoCleanupPendingError,
    BodyPhotoService,
    BodyPhotoSessionNotFoundError,
    BodyPhotoSessionStateError,
    BodyPhotoSessionValidationError,
)
from app.body_photos.storage import BodyPhotoStorageError
from app.config import Settings, get_settings
from app.database.session import get_db

router = APIRouter(prefix="/api/v1/body-photo-sessions", tags=["body-photos"])

DatabaseSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def _latest_consent(
    session: BodyPhotoSession,
    consent_type: BodyPhotoConsentType,
) -> BodyPhotoConsent | None:
    matching = [event for event in session.consents if event.consent_type is consent_type]
    return matching[-1] if matching else None


def _consent_response(event: BodyPhotoConsent | None) -> BodyPhotoConsentResponse | None:
    if event is None:
        return None
    return BodyPhotoConsentResponse(
        granted=event.granted,
        version=event.version,
        recorded_at=event.recorded_at,
    )


def _session_response(session: BodyPhotoSession) -> BodyPhotoSessionResponse:
    return BodyPhotoSessionResponse(
        id=session.id,
        purpose=session.purpose,
        state=session.state,
        photos=[
            BodyPhotoResponse(
                id=photo.id,
                view=photo.view,
                mime_type=photo.mime_type,
                byte_size=photo.byte_size,
                width=photo.width,
                height=photo.height,
                crop_confidence=photo.crop_confidence,
                client_crop_confirmed=photo.client_crop_confirmed,
                server_geometry_checked=photo.server_geometry_checked,
                content_url=(
                    f"/api/v1/body-photo-sessions/{session.id}/photos/{photo.view.value}/content"
                ),
                created_at=photo.created_at,
                updated_at=photo.updated_at,
            )
            for photo in sorted(session.photos, key=lambda item: item.view.value)
        ],
        operational_processing_consent=_consent_response(
            _latest_consent(session, BodyPhotoConsentType.OPERATIONAL_PROCESSING)
        ),
        model_training_consent=_consent_response(
            _latest_consent(session, BodyPhotoConsentType.MODEL_TRAINING)
        ),
        submitted_at=session.submitted_at,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Body photo session not found"
    )


@router.post(
    "",
    response_model=BodyPhotoSessionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def create_session(
    payload: BodyPhotoSessionCreate,
    db: DatabaseSession,
    user: CurrentUser,
    settings: AppSettings,
) -> BodyPhotoSessionResponse:
    return _session_response(
        BodyPhotoService(db, settings).create_session(user.id, payload.purpose)
    )


@router.get("", response_model=BodyPhotoSessionListResponse)
def list_sessions(
    db: DatabaseSession,
    user: CurrentUser,
    settings: AppSettings,
) -> BodyPhotoSessionListResponse:
    sessions = BodyPhotoService(db, settings).list_sessions(user.id)
    return BodyPhotoSessionListResponse(items=[_session_response(item) for item in sessions])


@router.get("/{session_id}", response_model=BodyPhotoSessionResponse)
def get_session(
    session_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
    settings: AppSettings,
) -> BodyPhotoSessionResponse:
    try:
        return _session_response(BodyPhotoService(db, settings).get_session(session_id, user.id))
    except BodyPhotoSessionNotFoundError:
        raise _not_found() from None


@router.put(
    "/{session_id}/photos/{view}",
    response_model=BodyPhotoSessionResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def upload_photo(
    session_id: UUID,
    view: BodyPhotoView,
    db: DatabaseSession,
    user: CurrentUser,
    settings: AppSettings,
    file: Annotated[UploadFile, File()],
    client_crop_confirmed: Annotated[
        str | None,
        Header(alias="X-Fitsho-Client-Crop-Confirmed"),
    ] = None,
    crop_confidence: Annotated[str | None, Header(alias="X-Fitsho-Crop-Confidence")] = None,
    original_height: Annotated[str | None, Header(alias="X-Fitsho-Original-Height")] = None,
    crop_top: Annotated[str | None, Header(alias="X-Fitsho-Crop-Top")] = None,
    crop_bottom: Annotated[str | None, Header(alias="X-Fitsho-Crop-Bottom")] = None,
    processed_sha256: Annotated[str | None, Header(alias="X-Fitsho-Processed-SHA256")] = None,
    crop_evidence_sha256: Annotated[
        str | None,
        Header(alias="X-Fitsho-Crop-Evidence-SHA256"),
    ] = None,
) -> BodyPhotoSessionResponse:
    try:
        session = BodyPhotoService(db, settings).upload_processed_photo(
            session_id,
            user.id,
            view,
            file,
            client_crop_confirmed=client_crop_confirmed,
            crop_confidence=crop_confidence,
            original_height=original_height,
            crop_top=crop_top,
            crop_bottom=crop_bottom,
            processed_sha256=processed_sha256,
            crop_evidence_sha256=crop_evidence_sha256,
        )
        return _session_response(session)
    except BodyPhotoSessionNotFoundError:
        raise _not_found() from None
    except BodyPhotoValidationError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Body photo could not be accepted",
        ) from None
    except BodyPhotoSessionStateError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Body photo session cannot be changed",
        ) from None
    except BodyPhotoStorageError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable",
        ) from None


@router.post(
    "/{session_id}/submit",
    response_model=BodyPhotoSessionResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def submit_session(
    session_id: UUID,
    payload: BodyPhotoSubmit,
    db: DatabaseSession,
    user: CurrentUser,
    settings: AppSettings,
) -> BodyPhotoSessionResponse:
    try:
        return _session_response(
            BodyPhotoService(db, settings).submit(session_id, user.id, payload)
        )
    except BodyPhotoSessionNotFoundError:
        raise _not_found() from None
    except BodyPhotoSessionValidationError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Three body photos and operational consent are required",
        ) from None
    except BodyPhotoSessionStateError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Body photo session cannot be submitted",
        ) from None


@router.post(
    "/{session_id}/consents/model-training",
    response_model=BodyPhotoConsentResponse,
    dependencies=[Depends(require_trusted_origin)],
)
def record_training_consent(
    session_id: UUID,
    payload: BodyPhotoConsentInput,
    db: DatabaseSession,
    user: CurrentUser,
    settings: AppSettings,
) -> BodyPhotoConsentResponse:
    try:
        event = BodyPhotoService(db, settings).record_training_consent(
            session_id,
            user.id,
            payload,
        )
    except BodyPhotoSessionNotFoundError:
        raise _not_found() from None
    return BodyPhotoConsentResponse(
        granted=event.granted,
        version=event.version,
        recorded_at=event.recorded_at,
    )


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_trusted_origin)],
)
def delete_session(
    session_id: UUID,
    db: DatabaseSession,
    user: CurrentUser,
    settings: AppSettings,
) -> None:
    try:
        BodyPhotoService(db, settings).delete_session(session_id, user.id)
    except BodyPhotoSessionNotFoundError:
        raise _not_found() from None
    except BodyPhotoStorageError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable",
        ) from None
    except BodyPhotoCleanupPendingError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable",
        ) from None


@router.get("/{session_id}/photos/{view}/content")
def get_photo_content(
    session_id: UUID,
    view: BodyPhotoView,
    db: DatabaseSession,
    user: CurrentUser,
    settings: AppSettings,
) -> StreamingResponse:
    try:
        session = BodyPhotoService(db, settings).get_session(session_id, user.id)
    except BodyPhotoSessionNotFoundError:
        raise _not_found() from None
    photo = next((item for item in session.photos if item.view is view), None)
    if photo is None:
        raise _not_found()
    storage = BodyPhotoService(db, settings).storage
    try:
        handle = storage.open(photo.storage_key)
    except BodyPhotoStorageError:
        raise _not_found() from None

    def stream() -> Iterator[bytes]:
        with handle:
            while chunk := handle.read(settings.body_photo_read_chunk_bytes):
                yield chunk

    return StreamingResponse(
        stream(),
        media_type=photo.mime_type,
        headers={"Cache-Control": "private, no-store"},
    )
