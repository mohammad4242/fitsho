from __future__ import annotations

import os
import re
import tempfile
import warnings
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from uuid import UUID, uuid4

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.body_analysis.enums import SpecialistRole
from app.body_analysis.models import UserSpecialistRole
from app.config import Settings
from app.nutrition.enums import (
    NutritionLabRequestStatus,
    NutritionPlanReviewStatus,
    NutritionSupplementOrderStatus,
)
from app.nutrition.models import (
    NutritionLabRequest,
    NutritionPlanPhysicianReview,
    NutritionSupplementOrder,
    NutritionWeeklyPlan,
)
from app.profile.models import UserProfilePhoto
from app.workout_reviews.enums import WorkoutReviewStatus
from app.workout_reviews.models import WorkoutPlanReview

PROFILE_PHOTO_FORMATS = {
    "JPEG": ("image/jpeg", ".jpg"),
    "PNG": ("image/png", ".png"),
    "WEBP": ("image/webp", ".webp"),
}
PROFILE_PHOTO_SIGNATURES = {
    "JPEG": lambda data: data.startswith(b"\xff\xd8\xff"),
    "PNG": lambda data: data.startswith(b"\x89PNG\r\n\x1a\n"),
    "WEBP": lambda data: len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP",
}
_PROFILE_PHOTO_KEY_PATTERN = re.compile(
    r"^[a-f0-9]{2}/[A-Za-z0-9][A-Za-z0-9_-]*\.(jpg|png|webp)$"
)


class ProfilePhotoValidationError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ProfilePhotoStorageError(RuntimeError):
    pass


class ProfilePhotoNotFoundError(LookupError):
    pass


class ProfilePhotoAccessDeniedError(PermissionError):
    pass


@dataclass(frozen=True)
class NormalizedProfilePhoto:
    content: bytes
    mime_type: str
    extension: str
    width: int
    height: int


@dataclass(frozen=True)
class StoredProfilePhoto:
    key: str


def _read_limited(upload: UploadFile, settings: Settings) -> bytes:
    chunks: list[bytes] = []
    total = 0
    upload.file.seek(0)
    while chunk := upload.file.read(settings.profile_photo_read_chunk_bytes):
        total += len(chunk)
        if total > settings.profile_photo_max_bytes:
            raise ProfilePhotoValidationError("invalid_file_size")
        chunks.append(chunk)
    if total == 0:
        raise ProfilePhotoValidationError("invalid_image")
    return b"".join(chunks)


def _normalized_mode(image: Image.Image, image_format: str) -> Image.Image:
    if image_format == "JPEG":
        return image.convert("RGB")
    if image.mode in {"RGB", "RGBA"}:
        return image.copy()
    return image.convert("RGBA" if "transparency" in image.info else "RGB")


def validate_and_normalize_profile_photo(
    upload: UploadFile,
    settings: Settings,
) -> NormalizedProfilePhoto:
    if upload.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise ProfilePhotoValidationError("unsupported_format")
    content = _read_limited(upload, settings)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as probe:
                image_format = probe.format
                if image_format not in PROFILE_PHOTO_FORMATS:
                    raise ProfilePhotoValidationError("unsupported_format")
                mime_type, extension = PROFILE_PHOTO_FORMATS[image_format]
                if upload.content_type != mime_type or not PROFILE_PHOTO_SIGNATURES[
                    image_format
                ](content):
                    raise ProfilePhotoValidationError("invalid_image")
                width, height = probe.size
                if width != height or width < settings.profile_photo_min_dimension:
                    raise ProfilePhotoValidationError("invalid_geometry")
                if width * height > settings.profile_photo_max_pixels:
                    raise ProfilePhotoValidationError("image_too_large")
                probe.verify()

            with Image.open(BytesIO(content)) as decoded:
                decoded.load()
                oriented = ImageOps.exif_transpose(decoded)
                if (
                    oriented.width != oriented.height
                    or oriented.width < settings.profile_photo_min_dimension
                ):
                    raise ProfilePhotoValidationError("invalid_geometry")
                if oriented.width * oriented.height > settings.profile_photo_max_pixels:
                    raise ProfilePhotoValidationError("image_too_large")
                normalized = _normalized_mode(oriented, image_format)
                output = BytesIO()
                if image_format == "JPEG":
                    normalized.save(output, format="JPEG", quality=90, optimize=True)
                elif image_format == "PNG":
                    normalized.save(output, format="PNG", optimize=True)
                else:
                    normalized.save(output, format="WEBP", quality=90, method=6)
    except ProfilePhotoValidationError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ProfilePhotoValidationError("image_too_large") from error
    except (OSError, UnidentifiedImageError, ValueError) as error:
        raise ProfilePhotoValidationError("invalid_image") from error

    normalized_content = output.getvalue()
    if not normalized_content:
        raise ProfilePhotoValidationError("invalid_image")
    if len(normalized_content) > settings.profile_photo_max_bytes:
        raise ProfilePhotoValidationError("invalid_file_size")
    return NormalizedProfilePhoto(
        content=normalized_content,
        mime_type=mime_type,
        extension=extension,
        width=normalized.width,
        height=normalized.height,
    )


class ProfilePhotoStorage:
    def __init__(self, settings: Settings) -> None:
        self._root = settings.profile_photo_storage_root.resolve()

    def path_for(self, key: str) -> Path:
        if not isinstance(key, str) or not _PROFILE_PHOTO_KEY_PATTERN.fullmatch(key):
            raise ProfilePhotoStorageError("Invalid private storage key")
        relative = PurePosixPath(key)
        if relative.is_absolute() or len(relative.parts) != 2 or ".." in relative.parts:
            raise ProfilePhotoStorageError("Invalid private storage key")
        path = self._root.joinpath(*relative.parts)
        if not path.is_relative_to(self._root):
            raise ProfilePhotoStorageError("Invalid private storage key")
        return path

    def store(self, content: bytes, extension: str) -> StoredProfilePhoto:
        if extension not in {".jpg", ".png", ".webp"} or not content:
            raise ProfilePhotoStorageError("Invalid normalized profile photo")
        identifier = uuid4().hex
        key = f"{identifier[:2]}/{identifier}{extension}"
        final_path = self.path_for(key)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(final_path.parent, 0o755)
        except OSError:
            pass
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=final_path.parent,
                prefix=".profile-photo-",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.chmod(temporary_path, 0o644)
            os.replace(temporary_path, final_path)
        except OSError as error:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise ProfilePhotoStorageError("Private storage is temporarily unavailable") from error
        return StoredProfilePhoto(key=key)

    def open(self, key: str) -> BinaryIO:
        try:
            return self.path_for(key).open("rb")
        except (OSError, ProfilePhotoStorageError) as error:
            raise ProfilePhotoStorageError("Private profile photo is unavailable") from error

    def delete(self, key: str) -> None:
        try:
            self.path_for(key).unlink(missing_ok=True)
        except (OSError, ProfilePhotoStorageError) as error:
            raise ProfilePhotoStorageError("Private storage is temporarily unavailable") from error


def profile_photo_url(
    user_id: UUID,
    updated_at: datetime | None = None,
    version: str | None = None,
) -> str:
    cache_token = version
    if cache_token is not None:
        cache_token = PurePosixPath(cache_token).stem
    if cache_token is None and updated_at is not None:
        cache_token = str(int(updated_at.timestamp() * 1_000_000))
    suffix = f"?v={cache_token}" if cache_token is not None else ""
    return f"/api/v1/profile/photo/{user_id}{suffix}"


def can_view_profile_photo(db: Session, viewer_id: UUID, owner_id: UUID) -> bool:
    if viewer_id == owner_id:
        return True

    roles = set(
        db.scalars(
            select(UserSpecialistRole.role).where(UserSpecialistRole.user_id == viewer_id)
        ).all()
    )
    if SpecialistRole.COACH in roles:
        claimed_review = db.scalar(
            select(WorkoutPlanReview.id).where(
                WorkoutPlanReview.user_id == owner_id,
                WorkoutPlanReview.claimed_by_user_id == viewer_id,
                WorkoutPlanReview.status.in_(
                    [WorkoutReviewStatus.CLAIMED, WorkoutReviewStatus.APPROVED]
                ),
            )
        )
        if claimed_review is not None:
            return True

    if roles.intersection({SpecialistRole.DOCTOR, SpecialistRole.PHYSICIAN}):
        physician_review = db.scalar(
            select(NutritionPlanPhysicianReview.id)
            .join(
                NutritionWeeklyPlan,
                NutritionWeeklyPlan.id == NutritionPlanPhysicianReview.plan_id,
            )
            .where(
                NutritionWeeklyPlan.user_id == owner_id,
                NutritionPlanPhysicianReview.physician_user_id == viewer_id,
                NutritionPlanPhysicianReview.status.in_(
                    [
                        NutritionPlanReviewStatus.IN_REVIEW,
                        NutritionPlanReviewStatus.AWAITING_LAB_INFORMATION,
                        NutritionPlanReviewStatus.APPROVED,
                    ]
                ),
            )
        )
        if physician_review is not None:
            return True
        lab_request = db.scalar(
            select(NutritionLabRequest.id).where(
                NutritionLabRequest.user_id == owner_id,
                NutritionLabRequest.physician_user_id == viewer_id,
                NutritionLabRequest.status.in_(
                    [
                        NutritionLabRequestStatus.REQUESTED,
                        NutritionLabRequestStatus.UPLOADED,
                        NutritionLabRequestStatus.REVIEWED,
                    ]
                ),
            )
        )
        if lab_request is not None:
            return True
        supplement_order = db.scalar(
            select(NutritionSupplementOrder.id).where(
                NutritionSupplementOrder.user_id == owner_id,
                NutritionSupplementOrder.physician_user_id == viewer_id,
                NutritionSupplementOrder.status.in_(
                    [
                        NutritionSupplementOrderStatus.PRESCRIBED,
                        NutritionSupplementOrderStatus.ACTIVE,
                        NutritionSupplementOrderStatus.COMPLETED,
                        NutritionSupplementOrderStatus.DISCONTINUED,
                    ]
                ),
            )
        )
        if supplement_order is not None:
            return True
    return False


def authorized_profile_photo_url(
    db: Session,
    viewer_id: UUID,
    owner_id: UUID,
) -> str | None:
    if not can_view_profile_photo(db, viewer_id, owner_id):
        return None
    row = db.scalar(select(UserProfilePhoto).where(UserProfilePhoto.user_id == owner_id))
    return profile_photo_url(owner_id, row.updated_at, row.storage_key) if row is not None else None


class ProfilePhotoService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self._db = db
        self._storage = ProfilePhotoStorage(settings)
        self._settings = settings

    @property
    def storage(self) -> ProfilePhotoStorage:
        return self._storage

    def get(self, owner_id: UUID) -> UserProfilePhoto:
        row = self._db.scalar(
            select(UserProfilePhoto).where(UserProfilePhoto.user_id == owner_id)
        )
        if row is None:
            raise ProfilePhotoNotFoundError
        return row

    def save(self, owner_id: UUID, upload: UploadFile) -> UserProfilePhoto:
        normalized = validate_and_normalize_profile_photo(upload, self._settings)
        stored = self._storage.store(normalized.content, normalized.extension)
        old_key: str | None = None
        try:
            row = self._db.scalar(
                select(UserProfilePhoto)
                .where(UserProfilePhoto.user_id == owner_id)
                .with_for_update()
            )
            if row is None:
                row = UserProfilePhoto(
                    user_id=owner_id,
                    storage_key=stored.key,
                    mime_type=normalized.mime_type,
                    byte_size=len(normalized.content),
                    width=normalized.width,
                    height=normalized.height,
                )
                self._db.add(row)
            else:
                old_key = row.storage_key
                row.storage_key = stored.key
                row.mime_type = normalized.mime_type
                row.byte_size = len(normalized.content)
                row.width = normalized.width
                row.height = normalized.height
            self._db.commit()
            self._db.refresh(row)
        except SQLAlchemyError:
            self._db.rollback()
            try:
                self._storage.delete(stored.key)
            except ProfilePhotoStorageError:
                pass
            raise
        if old_key is not None and old_key != stored.key:
            try:
                self._storage.delete(old_key)
            except ProfilePhotoStorageError:
                pass
        return row

    def delete(self, owner_id: UUID) -> None:
        row = self._db.scalar(
            select(UserProfilePhoto)
            .where(UserProfilePhoto.user_id == owner_id)
            .with_for_update()
        )
        if row is None:
            raise ProfilePhotoNotFoundError
        key = row.storage_key
        self._db.delete(row)
        self._db.commit()
        try:
            self._storage.delete(key)
        except ProfilePhotoStorageError:
            pass

    def open_for(self, viewer_id: UUID, owner_id: UUID) -> tuple[UserProfilePhoto, BinaryIO]:
        if not can_view_profile_photo(self._db, viewer_id, owner_id):
            raise ProfilePhotoAccessDeniedError
        row = self.get(owner_id)
        try:
            handle = self._storage.open(row.storage_key)
        except ProfilePhotoStorageError as error:
            raise ProfilePhotoNotFoundError from error
        return row, handle
