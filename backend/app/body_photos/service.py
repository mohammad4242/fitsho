from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.body_photos.enums import (
    BodyPhotoCleanupReason,
    BodyPhotoConsentType,
    BodyPhotoPurpose,
    BodyPhotoSessionState,
    BodyPhotoView,
)
from app.body_photos.image_validation import NormalizedBodyPhoto, validate_and_normalize
from app.body_photos.models import (
    BodyPhoto,
    BodyPhotoConsent,
    BodyPhotoSession,
    BodyPhotoStorageCleanup,
)
from app.body_photos.schemas import BodyPhotoConsentInput, BodyPhotoSubmit
from app.body_photos.storage import (
    BodyPhotoStorage,
    BodyPhotoStorageError,
    BodyPhotoStorageProtocol,
)
from app.config import Settings
from app.database.session import get_engine

EDITABLE_STATES = {
    BodyPhotoSessionState.DRAFT,
    BodyPhotoSessionState.AWAITING_CONSENT,
    BodyPhotoSessionState.UPLOADING,
    BodyPhotoSessionState.UPLOADED,
    BodyPhotoSessionState.FAILED,
}


class BodyPhotoSessionNotFoundError(LookupError):
    pass


class BodyPhotoSessionValidationError(ValueError):
    pass


class BodyPhotoSessionStateError(ValueError):
    pass


class BodyPhotoCleanupPendingError(RuntimeError):
    pass


CleanupSessionFactory = Callable[[], Session]


class BodyPhotoService:
    def __init__(
        self,
        db: Session,
        settings: Settings,
        storage: BodyPhotoStorageProtocol | None = None,
        cleanup_session_factory: CleanupSessionFactory | None = None,
    ) -> None:
        self._db = db
        self.storage = storage or BodyPhotoStorage(settings)
        self._settings = settings
        self._cleanup_session_factory = cleanup_session_factory or (
            lambda: Session(get_engine(settings.database_url))
        )

    def _owner_session(
        self,
        session_id: UUID,
        user_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> BodyPhotoSession:
        conditions = [
            BodyPhotoSession.id == session_id,
            BodyPhotoSession.user_id == user_id,
        ]
        if not include_deleted:
            conditions.append(BodyPhotoSession.state != BodyPhotoSessionState.DELETED)
        session = self._db.scalar(
            select(BodyPhotoSession)
            .where(*conditions)
            .options(
                selectinload(BodyPhotoSession.photos),
                selectinload(BodyPhotoSession.consents),
                selectinload(BodyPhotoSession.storage_cleanups),
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

    def upload_standardized_photo(
        self,
        session_id: UUID,
        user_id: UUID,
        view: BodyPhotoView,
        upload: UploadFile,
    ) -> BodyPhotoSession:
        session = self._owner_session(session_id, user_id)
        if session.state not in EDITABLE_STATES and not self._queued_session_has_failed_analysis(
            session.id
        ):
            raise BodyPhotoSessionStateError
        self._drain_pending_cleanup(session)
        normalized = validate_and_normalize(upload, self._settings)
        return self._store_photo(session, view, normalized)

    def _queued_session_has_failed_analysis(self, session_id: UUID) -> bool:
        from app.body_analysis.enums import BodyAnalysisStatus
        from app.body_analysis.models import BodyAnalysis

        latest_status = self._db.scalar(
            select(BodyAnalysis.status)
            .where(BodyAnalysis.session_id == session_id)
            .order_by(BodyAnalysis.revision.desc())
            .limit(1)
        )
        return latest_status is BodyAnalysisStatus.FAILED

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
        if old_key is not None:
            self._queue_cleanup(session, old_key, BodyPhotoCleanupReason.REPLACEMENT)
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
            try:
                self.storage.delete(stored.key)
            except BodyPhotoStorageError:
                self._persist_failed_upload_cleanup(session.id, stored.key)
            raise
        refreshed = self._owner_session(session.id, session.user_id)
        self._drain_pending_cleanup(refreshed)
        return self._owner_session(session.id, session.user_id)

    def _persist_failed_upload_cleanup(self, session_id: UUID, storage_key: str) -> None:
        with self._cleanup_session_factory() as cleanup_db:
            existing = cleanup_db.scalar(
                select(BodyPhotoStorageCleanup).where(
                    BodyPhotoStorageCleanup.storage_key == storage_key
                )
            )
            if existing is None:
                cleanup_db.add(
                    BodyPhotoStorageCleanup(
                        session_id=session_id,
                        storage_key=storage_key,
                        reason=BodyPhotoCleanupReason.FAILED_UPLOAD_ROLLBACK,
                    )
                )
            try:
                cleanup_db.commit()
            except SQLAlchemyError:
                cleanup_db.rollback()
                raise

    def _queue_cleanup(
        self,
        session: BodyPhotoSession,
        storage_key: str,
        reason: BodyPhotoCleanupReason,
    ) -> None:
        if any(item.storage_key == storage_key for item in session.storage_cleanups):
            return
        session.storage_cleanups.append(
            BodyPhotoStorageCleanup(storage_key=storage_key, reason=reason)
        )

    def _drain_pending_cleanup(self, session: BodyPhotoSession) -> bool:
        failed = False
        for cleanup in list(session.storage_cleanups):
            try:
                self.storage.delete(cleanup.storage_key)
            except BodyPhotoStorageError:
                cleanup.attempts += 1
                cleanup.last_attempt_at = datetime.now(UTC)
                failed = True
            else:
                self._db.delete(cleanup)
        try:
            self._db.commit()
        except SQLAlchemyError:
            self._db.rollback()
            raise
        return not failed

    def retry_pending_cleanup(self, session_id: UUID, user_id: UUID) -> bool:
        session = self._owner_session(session_id, user_id, include_deleted=True)
        return self._drain_pending_cleanup(session)

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
        session = self._owner_session(session_id, user_id, include_deleted=True)
        if session.state is not BodyPhotoSessionState.DELETED:
            for photo in list(session.photos):
                self._queue_cleanup(
                    session,
                    photo.storage_key,
                    BodyPhotoCleanupReason.SESSION_DELETE,
                )
                self._db.delete(photo)
            session.state = BodyPhotoSessionState.DELETED
            session.deleted_at = datetime.now(UTC)
            try:
                self._db.commit()
            except SQLAlchemyError:
                self._db.rollback()
                raise
            session = self._owner_session(session_id, user_id, include_deleted=True)
        if not self._drain_pending_cleanup(session):
            raise BodyPhotoCleanupPendingError
