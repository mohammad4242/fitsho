from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from app.config import Settings


class PrivateMediaError(ValueError):
    def __init__(self) -> None:
        super().__init__("invalid private media reference")


class PrivateMediaResolver:
    """Resolve Backend-owned private media keys beneath configured roots."""

    _MIME_SUFFIXES = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    _DIRECTORY_PATTERN = re.compile(r"^[a-f0-9]{2}$")
    _FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*\.(jpg|png|webp)$")

    def __init__(self, settings: Settings) -> None:
        self._roots = {
            "body": settings.body_photo_storage_root.resolve(),
            "food": settings.food_photo_storage_root.resolve(),
        }

    def resolve(self, scope: str, storage_key: str, expected_mime_type: str) -> Path:
        root = self._roots.get(scope)
        suffix = self._MIME_SUFFIXES.get(expected_mime_type)
        if root is None or suffix is None:
            raise PrivateMediaError
        parts = self._validated_parts(storage_key)
        if not parts[1].endswith(suffix):
            raise PrivateMediaError
        try:
            resolved_root = root.resolve(strict=True)
            if not resolved_root.is_dir():
                raise PrivateMediaError
            resolved = resolved_root.joinpath(*parts).resolve(strict=True)
            if not resolved.is_relative_to(resolved_root) or not resolved.is_file():
                raise PrivateMediaError
            return resolved
        except (OSError, RuntimeError, ValueError) as error:
            raise PrivateMediaError from error

    def read(self, scope: str, storage_key: str, expected_mime_type: str) -> bytes:
        path = self.resolve(scope, storage_key, expected_mime_type)
        try:
            return path.read_bytes()
        except (OSError, RuntimeError) as error:
            raise PrivateMediaError from error

    @classmethod
    def _validated_parts(cls, storage_key: str) -> tuple[str, str]:
        if not isinstance(storage_key, str) or not storage_key or "\x00" in storage_key:
            raise PrivateMediaError
        if "\\" in storage_key:
            raise PrivateMediaError
        raw_parts = storage_key.split("/")
        if len(raw_parts) != 2 or any(part in {"", ".", ".."} for part in raw_parts):
            raise PrivateMediaError
        relative = PurePosixPath(storage_key)
        if relative.is_absolute() or len(relative.parts) != 2 or ".." in relative.parts:
            raise PrivateMediaError
        directory, filename = raw_parts
        if not cls._DIRECTORY_PATTERN.fullmatch(directory):
            raise PrivateMediaError
        if not cls._FILENAME_PATTERN.fullmatch(filename):
            raise PrivateMediaError
        return directory, filename
