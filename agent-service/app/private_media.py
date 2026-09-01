from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

from .schemas import StoredImageReference

_KEY_PARTS = re.compile(r"^[a-f0-9]{2}$")
_KEY_FILENAME = re.compile(r"^[a-f0-9]{32}\.(?:jpg|png|webp)$")
_MIME_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class PrivateMediaError(ValueError):
    """A safe, non-path-bearing private-media resolution failure."""


class PrivateMediaResolver:
    def __init__(
        self,
        root: Path,
        *,
        max_images: int = 5,
        max_file_bytes: int = 8 * 1024 * 1024,
        max_total_bytes: int = 20 * 1024 * 1024,
    ) -> None:
        self.root = Path(root)
        self.max_images = max_images
        self.max_file_bytes = max_file_bytes
        self.max_total_bytes = max_total_bytes

    def resolve(self, scope: str, storage_key: str, mime_type: str) -> Path:
        scope_root = self._scope_root(scope)
        self._validate_key(storage_key, mime_type)
        try:
            resolved_base = self.root.resolve(strict=True)
            resolved_root = scope_root.resolve(strict=True)
            resolved_path = (scope_root / storage_key).resolve(strict=True)
        except (OSError, RuntimeError, ValueError) as exc:
            raise PrivateMediaError("invalid private media reference") from exc
        if (
            not resolved_base.is_dir()
            or not resolved_root.is_dir()
            or not resolved_root.is_relative_to(resolved_base)
            or not resolved_path.is_file()
        ):
            raise PrivateMediaError("invalid private media reference")
        try:
            contained = resolved_path.is_relative_to(resolved_root)
        except (OSError, RuntimeError, ValueError) as exc:
            raise PrivateMediaError("invalid private media reference") from exc
        if not contained:
            raise PrivateMediaError("invalid private media reference")
        try:
            size = resolved_path.stat().st_size
        except (OSError, RuntimeError, ValueError) as exc:
            raise PrivateMediaError("invalid private media reference") from exc
        if size > self.max_file_bytes:
            raise PrivateMediaError("invalid private media reference")
        return resolved_path

    def resolve_many(self, references: Sequence[StoredImageReference]) -> tuple[Path, ...]:
        if not references or len(references) > self.max_images:
            raise PrivateMediaError("invalid private media reference")
        paths = tuple(
            self.resolve(reference.storage_scope, reference.storage_key, reference.mime_type)
            for reference in references
        )
        try:
            total_size = sum(path.stat().st_size for path in paths)
        except (OSError, RuntimeError, ValueError) as exc:
            raise PrivateMediaError("invalid private media reference") from exc
        if total_size > self.max_total_bytes:
            raise PrivateMediaError("invalid private media reference")
        return paths

    def _scope_root(self, scope: str) -> Path:
        if scope not in {"body", "food"}:
            raise PrivateMediaError("invalid private media reference")
        return self.root / scope

    @staticmethod
    def _validate_key(storage_key: str, mime_type: str) -> None:
        expected_extension = _MIME_EXTENSIONS.get(mime_type)
        if expected_extension is None:
            raise PrivateMediaError("invalid private media reference")
        if not isinstance(storage_key, str) or "\x00" in storage_key:
            raise PrivateMediaError("invalid private media reference")
        if storage_key.startswith("/") or "\\" in storage_key:
            raise PrivateMediaError("invalid private media reference")
        parts = storage_key.split("/")
        if len(parts) != 2 or any(not part or part in {".", ".."} for part in parts):
            raise PrivateMediaError("invalid private media reference")
        directory, filename = parts
        if _KEY_PARTS.fullmatch(directory) is None or _KEY_FILENAME.fullmatch(filename) is None:
            raise PrivateMediaError("invalid private media reference")
        if directory != filename[:2]:
            raise PrivateMediaError("invalid private media reference")
        if not filename.endswith(expected_extension):
            raise PrivateMediaError("invalid private media reference")
