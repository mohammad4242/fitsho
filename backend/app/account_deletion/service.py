from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.account_deletion.models import AccountDeletionRequest, AccountDeletionStatus
from app.auth.dependencies import AuthenticatedPrincipal
from app.auth.models import (
    AuthSession,
    MobileAccessToken,
    MobileRefreshToken,
    MobileTokenFamily,
    User,
)
from app.auth.security import verify_password
from app.body_photos.models import BodyPhoto, BodyPhotoSession, BodyPhotoStorageCleanup
from app.body_photos.storage import BodyPhotoStorage, BodyPhotoStorageError
from app.config import Settings
from app.nutrition.clinical_service import ClinicalError, lab_storage_path
from app.nutrition.food_photo_service import FoodPhotoError, food_photo_storage_path
from app.nutrition.models import NutritionFoodPhotoEstimate, NutritionLabDocument
from app.profile.models import UserProfilePhoto
from app.profile.photo import ProfilePhotoStorage, ProfilePhotoStorageError


class AccountDeletionError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class AccountDeletionExecutionError(RuntimeError):
    pass


@dataclass(frozen=True)
class AccountDeletionResult:
    request: AccountDeletionRequest


def _current_time(now: datetime | None) -> datetime:
    return now or datetime.now(UTC)


def _ensure_enabled(settings: Settings) -> None:
    if not settings.account_deletion_enabled:
        raise AccountDeletionError("ACCOUNT_DELETION_NOT_ENABLED")


def _ensure_reauthenticated(
    principal: AuthenticatedPrincipal,
    password: str | None,
    settings: Settings,
    now: datetime,
) -> None:
    if principal.user.password_hash is not None:
        if password is None or not verify_password(password, principal.user.password_hash):
            raise AccountDeletionError("INVALID_REAUTHENTICATION")
        return
    if principal.authenticated_at is None or principal.authenticated_at < (
        now - timedelta(seconds=settings.account_deletion_reauth_window_seconds)
    ):
        raise AccountDeletionError("RECENT_AUTHENTICATION_REQUIRED")


def _latest_request(
    db: Session,
    user_id: UUID,
    *,
    lock: bool = False,
) -> AccountDeletionRequest | None:
    statement = (
        select(AccountDeletionRequest)
        .where(AccountDeletionRequest.user_id == user_id)
        .order_by(AccountDeletionRequest.requested_at.desc(), AccountDeletionRequest.id.desc())
    )
    if lock:
        statement = statement.with_for_update()
    return db.scalar(statement)


def initiate_deletion(
    db: Session,
    principal: AuthenticatedPrincipal,
    settings: Settings,
    *,
    password: str | None,
    now: datetime | None = None,
) -> AccountDeletionResult:
    _ensure_enabled(settings)
    current = _current_time(now)
    _ensure_reauthenticated(principal, password, settings, current)

    existing = db.scalar(
        select(AccountDeletionRequest)
        .where(
            AccountDeletionRequest.user_id == principal.user.id,
            AccountDeletionRequest.status == AccountDeletionStatus.PENDING,
        )
        .order_by(AccountDeletionRequest.requested_at.desc(), AccountDeletionRequest.id.desc())
        .with_for_update()
    )
    if existing is not None:
        return AccountDeletionResult(existing)

    deletion = AccountDeletionRequest(
        user_id=principal.user.id,
        status=AccountDeletionStatus.PENDING,
        requested_at=current,
        reauthenticated_at=current,
        grace_period_ends_at=current + timedelta(days=settings.account_deletion_grace_period_days),
    )
    db.add(deletion)
    try:
        db.commit()
        db.refresh(deletion)
    except SQLAlchemyError:
        db.rollback()
        raise
    return AccountDeletionResult(deletion)


def get_deletion_status(
    db: Session,
    user_id: UUID,
    settings: Settings,
) -> AccountDeletionRequest | None:
    _ensure_enabled(settings)
    return _latest_request(db, user_id)


def cancel_deletion(
    db: Session,
    user_id: UUID,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> AccountDeletionResult:
    _ensure_enabled(settings)
    current = _current_time(now)
    deletion = db.scalar(
        select(AccountDeletionRequest)
        .where(
            AccountDeletionRequest.user_id == user_id,
            AccountDeletionRequest.status == AccountDeletionStatus.PENDING,
        )
        .order_by(AccountDeletionRequest.requested_at.desc(), AccountDeletionRequest.id.desc())
        .with_for_update()
    )
    if deletion is None:
        raise AccountDeletionError("NO_PENDING_DELETION")
    if deletion.grace_period_ends_at <= current:
        raise AccountDeletionError("GRACE_PERIOD_EXPIRED")
    deletion.status = AccountDeletionStatus.CANCELLED
    deletion.cancelled_at = current
    try:
        db.commit()
        db.refresh(deletion)
    except SQLAlchemyError:
        db.rollback()
        raise
    return AccountDeletionResult(deletion)


def _unlink(path: Path, *, resource: str) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        raise AccountDeletionExecutionError(
            f"Unable to delete private {resource} storage object"
        ) from error


def _delete_private_files(db: Session, settings: Settings, user_id: UUID) -> None:
    body_storage = BodyPhotoStorage(settings)
    body_keys = set(
        db.scalars(
            select(BodyPhoto.storage_key)
            .join(BodyPhotoSession, BodyPhotoSession.id == BodyPhoto.session_id)
            .where(BodyPhotoSession.user_id == user_id)
        ).all()
    )
    body_keys.update(
        db.scalars(
            select(BodyPhotoStorageCleanup.storage_key)
            .join(BodyPhotoSession, BodyPhotoSession.id == BodyPhotoStorageCleanup.session_id)
            .where(BodyPhotoSession.user_id == user_id)
        ).all()
    )
    for key in body_keys:
        try:
            body_storage.delete(key)
        except BodyPhotoStorageError as error:
            raise AccountDeletionExecutionError(
                "Unable to delete private body photo storage object"
            ) from error

    profile_storage = ProfilePhotoStorage(settings)
    profile_key = db.scalar(
        select(UserProfilePhoto.storage_key).where(UserProfilePhoto.user_id == user_id)
    )
    if profile_key is not None:
        try:
            profile_storage.delete(profile_key)
        except ProfilePhotoStorageError as error:
            raise AccountDeletionExecutionError(
                "Unable to delete private profile photo storage object"
            ) from error

    food_keys = db.scalars(
        select(NutritionFoodPhotoEstimate.storage_key).where(
            NutritionFoodPhotoEstimate.user_id == user_id
        )
    ).all()
    for key in food_keys:
        try:
            _unlink(
                food_photo_storage_path(settings.food_photo_storage_root, key),
                resource="food photo",
            )
        except FoodPhotoError as error:
            raise AccountDeletionExecutionError("Invalid private food photo storage key") from error

    lab_keys = db.scalars(
        select(NutritionLabDocument.storage_key).where(NutritionLabDocument.user_id == user_id)
    ).all()
    for key in lab_keys:
        try:
            _unlink(lab_storage_path(settings.nutrition_lab_storage_root, key), resource="lab")
        except ClinicalError as error:
            raise AccountDeletionExecutionError("Invalid private lab storage key") from error


def _revoke_auth_state(db: Session, user_id: UUID, now: datetime) -> None:
    families = db.scalars(
        select(MobileTokenFamily).where(MobileTokenFamily.user_id == user_id)
    ).all()
    family_ids = [family.id for family in families]
    for family in families:
        family.revoked_at = family.revoked_at or now
        family.revoke_reason = family.revoke_reason or "account_deletion"
    if family_ids:
        db.execute(
            update(MobileAccessToken)
            .where(MobileAccessToken.family_id.in_(family_ids))
            .values(revoked_at=now)
        )
        db.execute(
            update(MobileRefreshToken)
            .where(MobileRefreshToken.family_id.in_(family_ids))
            .values(revoked_at=now)
        )
    db.execute(delete(AuthSession).where(AuthSession.user_id == user_id))


def _execute_one(
    db: Session,
    settings: Settings,
    deletion: AccountDeletionRequest,
    now: datetime,
) -> None:
    user_id = deletion.user_id
    if user_id is None:
        deletion.status = AccountDeletionStatus.COMPLETED
        deletion.completed_at = deletion.completed_at or now
        return
    user = db.get(User, user_id)
    if user is None:
        deletion.user_id = None
        deletion.status = AccountDeletionStatus.COMPLETED
        deletion.completed_at = deletion.completed_at or now
        return
    _delete_private_files(db, settings, user_id)
    _revoke_auth_state(db, user_id, now)
    db.execute(delete(User).where(User.id == user_id))
    deletion.user_id = None
    deletion.status = AccountDeletionStatus.COMPLETED
    deletion.completed_at = now


def execute_due_account_deletions(
    db: Session,
    settings: Settings,
    *,
    now: datetime | None = None,
    batch_size: int = 50,
) -> int:
    _ensure_enabled(settings)
    current = _current_time(now)
    deletions = db.scalars(
        select(AccountDeletionRequest)
        .where(
            AccountDeletionRequest.status == AccountDeletionStatus.PENDING,
            AccountDeletionRequest.grace_period_ends_at <= current,
        )
        .order_by(AccountDeletionRequest.grace_period_ends_at, AccountDeletionRequest.id)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    ).all()
    processed = 0
    for deletion in deletions:
        try:
            _execute_one(db, settings, deletion, current)
            db.commit()
        except (AccountDeletionExecutionError, SQLAlchemyError):
            db.rollback()
            raise
        processed += 1
    return processed
