from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from uuid import uuid4

from app.config import Settings


class BodyPhotoStorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredBodyPhoto:
    key: str
    path: Path


class BodyPhotoStorage:
    def __init__(self, settings: Settings) -> None:
        self._root = settings.body_photo_storage_root.resolve()

    def _path_for(self, key: str) -> Path:
        relative = PurePosixPath(key)
        if relative.is_absolute() or len(relative.parts) != 2 or ".." in relative.parts:
            raise BodyPhotoStorageError("Invalid private storage key")
        path = self._root.joinpath(*relative.parts)
        if not path.is_relative_to(self._root):
            raise BodyPhotoStorageError("Invalid private storage key")
        return path

    def store(self, content: bytes, extension: str) -> StoredBodyPhoto:
        if extension not in {".jpg", ".png", ".webp"} or not content:
            raise BodyPhotoStorageError("Invalid normalized body photo")
        identifier = uuid4().hex
        key = f"{identifier[:2]}/{identifier}{extension}"
        final_path = self._path_for(key)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=final_path.parent,
                prefix=".body-photo-",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, final_path)
        except OSError as error:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise BodyPhotoStorageError("Private storage is temporarily unavailable") from error
        return StoredBodyPhoto(key=key, path=final_path)

    def open(self, key: str) -> BinaryIO:
        try:
            return self._path_for(key).open("rb")
        except (OSError, BodyPhotoStorageError) as error:
            raise BodyPhotoStorageError("Private body photo is unavailable") from error

    def delete(self, key: str) -> None:
        try:
            self._path_for(key).unlink(missing_ok=True)
        except (OSError, BodyPhotoStorageError) as error:
            raise BodyPhotoStorageError("Private storage is temporarily unavailable") from error
