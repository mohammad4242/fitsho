from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.body_photos.enums import (
    BodyPhotoConsentType,
    BodyPhotoPurpose,
    BodyPhotoSessionState,
    BodyPhotoView,
)
from app.body_photos.image_validation import NormalizedBodyPhoto, validate_and_normalize
from app.body_photos.models import BodyPhoto, BodyPhotoConsent, BodyPhotoSession
from app.body_photos.schemas import BodyPhotoConsentInput, BodyPhotoSubmit
from app.body_photos.storage import BodyPhotoStorage
from app.config import Settings

EDITABLE_STATES = {
    BodyPhotoSessionState.DRAFT,
    BodyPhotoSessionState.AWAITING_CONSENT,
    BodyPhotoSessionState.UPLOADING,
    BodyPhotoSessionState.UPLOADED,
}


class BodyPhotoSessionNotFoundError(LookupError):
    pass


class BodyPhotoSessionValidationError(ValueError):
    pass


class BodyPhotoSessionStateError(ValueError):
    pass


class BodyPhotoService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self._db = db
        self.storage = BodyPhotoStorage(settings)
        self._settings = settings

    def _owner_session(self, session_id: UUID, user_id: UUID) -> BodyPhotoSession:
        session = self._db.scalar(
            select(BodyPhotoSession)
            .where(
                BodyPhotoSession.id == session_id,
                BodyPhotoSession.user_id == user_id,
                BodyPhotoSession.state != BodyPhotoSessionState.DELETED,
            )
            .options(
                selectinload(BodyPhotoSession.photos),
                selectinload(BodyPhotoSession.consents),
            )
        )
        if session is None:
            raise BodyPhotoSessionNotFoundError
        return session

    def create_session(self, user_id: UUID, purpose: BodyPhotoPurpose) -> BodyPhotoSession:
        session = BodyPhotoSession(user_id=user_id, purpose=purpose)
        self._db.add(session)
        try:
            self._db.commit()
            self._db.refresh(session)
        except SQLAlchemyError:
            self._db.rollback()
            raise
        return self._owner_session(session.id, user_id)

    def list_sessions(self, user_id: UUID) -> list[BodyPhotoSession]:
        return list(
            self._db.scalars(
                select(BodyPhotoSession)
                .where(
                    BodyPhotoSession.user_id == user_id,
                    BodyPhotoSession.state != BodyPhotoSessionState.DELETED,
                )
                .options(
                    selectinload(BodyPhotoSession.photos),
                    selectinload(BodyPhotoSession.consents),
                )
                .order_by(BodyPhotoSession.created_at.desc())
            ).all()
        )

    def get_session(self, session_id: UUID, user_id: UUID) -> BodyPhotoSession:
        return self._owner_session(session_id, user_id)

    def upload_processed_photo(
        self,
        session_id: UUID,
        user_id: UUID,
        view: BodyPhotoView,
        upload: UploadFile,
        *,
        head_cropped: str | None,
        crop_confidence: str | None,
    ) -> BodyPhotoSession:
        session = self._owner_session(session_id, user_id)
        if session.state not in EDITABLE_STATES:
            raise BodyPhotoSessionStateError
        normalized = validate_and_normalize(
            upload,
            self._settings,
            head_cropped=head_cropped,
            crop_confidence=crop_confidence,
        )
        return self._store_photo(session, view, normalized)

    def _store_photo(
        self,
        session: BodyPhotoSession,
        view: BodyPhotoView,
        normalized: NormalizedBodyPhoto,
    ) -> BodyPhotoSession:
        stored = self.storage.store(normalized.content, normalized.extension)
        existing = next((photo for photo in session.photos if photo.view is view), None)
        old_key = existing.storage_key if existing is not None else None
        if existing is None:
            existing = BodyPhoto(session_id=session.id, view=view, storage_key=stored.key)
            self._db.add(existing)
        existing.storage_key = stored.key
        existing.mime_type = normalized.mime_type
        existing.byte_size = len(normalized.content)
        existing.width = normalized.width
        existing.height = normalized.height
        existing.crop_confidence = normalized.crop_confidence
        existing.crop_geometry_verified = normalized.crop_geometry_verified
        session.state = BodyPhotoSessionState.UPLOADING
        try:
            self._db.flush()
            views = set(
                self._db.scalars(
                    select(BodyPhoto.view).where(BodyPhoto.session_id == session.id)
                ).all()
            )
            if views == set(BodyPhotoView):
                session.state = BodyPhotoSessionState.UPLOADED
            self._db.commit()
        except SQLAlchemyError:
            self._db.rollback()
            self.storage.delete(stored.key)
            raise
        if old_key is not None:
            self.storage.delete(old_key)
        return self._owner_session(session.id, session.user_id)

    def submit(
        self,
        session_id: UUID,
        user_id: UUID,
        payload: BodyPhotoSubmit,
    ) -> BodyPhotoSession:
        session = self._owner_session(session_id, user_id)
        if session.state is BodyPhotoSessionState.QUEUED:
            return session
        if session.state not in EDITABLE_STATES:
            raise BodyPhotoSessionStateError
        if {photo.view for photo in session.photos} != set(BodyPhotoView):
            raise BodyPhotoSessionValidationError
        if not payload.operational_processing.granted:
            raise BodyPhotoSessionValidationError

        self._append_consent(
            session,
            BodyPhotoConsentType.OPERATIONAL_PROCESSING,
            payload.operational_processing,
        )
        self._append_consent(session, BodyPhotoConsentType.MODEL_TRAINING, payload.model_training)
        session.state = BodyPhotoSessionState.QUEUED
        session.submitted_at = datetime.now(UTC)
        try:
            self._db.commit()
        except SQLAlchemyError:
            self._db.rollback()
            raise
        return self._owner_session(session.id, user_id)

    def record_training_consent(
        self,
        session_id: UUID,
        user_id: UUID,
        consent: BodyPhotoConsentInput,
    ) -> BodyPhotoConsent:
        session = self._owner_session(session_id, user_id)
        event = self._append_consent(session, BodyPhotoConsentType.MODEL_TRAINING, consent)
        try:
            self._db.commit()
            self._db.refresh(event)
        except SQLAlchemyError:
            self._db.rollback()
            raise
        return event

    def _append_consent(
        self,
        session: BodyPhotoSession,
        consent_type: BodyPhotoConsentType,
        consent: BodyPhotoConsentInput,
    ) -> BodyPhotoConsent:
        event = BodyPhotoConsent(
            session_id=session.id,
            user_id=session.user_id,
            consent_type=consent_type,
            version=consent.version,
            granted=consent.granted,
        )
        self._db.add(event)
        return event

    def delete_session(self, session_id: UUID, user_id: UUID) -> None:
        session = self._owner_session(session_id, user_id)
        keys = [photo.storage_key for photo in session.photos]
        session.state = BodyPhotoSessionState.DELETED
        session.deleted_at = datetime.now(UTC)
        for photo in list(session.photos):
            self._db.delete(photo)
        try:
            self._db.commit()
        except SQLAlchemyError:
            self._db.rollback()
            raise
        for key in keys:
            self.storage.delete(key)
