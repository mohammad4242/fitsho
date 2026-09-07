from __future__ import annotations

import os
import re
import tempfile
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import Settings

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
