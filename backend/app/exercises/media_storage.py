from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings


class ExerciseMediaStorageError(ValueError):
    """Raised when a deterministic exercise-media destination is unsafe to publish."""


@dataclass(frozen=True)
class StoredExerciseMedia:
    public_path: str
    absolute_path: Path
    created: bool


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        while chunk := file_handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_existing_destination(destination: Path, expected_digest: str) -> None:
    if not destination.is_file():
        raise ExerciseMediaStorageError("Existing exercise media destination is not a file")
    try:
        actual_digest = sha256_file(destination)
    except OSError as error:
        raise ExerciseMediaStorageError(
            "Existing exercise media destination could not be verified"
        ) from error
    if actual_digest != expected_digest:
        raise ExerciseMediaStorageError(
            "Existing exercise media destination does not match content hash"
        )


def _validate_namespace(namespace: str) -> str:
    if (
        not isinstance(namespace, str)
        or not namespace
        or namespace in {".", ".."}
        or "\x00" in namespace
        or "/" in namespace
        or "\\" in namespace
        or Path(namespace).is_absolute()
    ):
        raise ExerciseMediaStorageError("Exercise media namespace must be a safe directory name")
    return namespace


def publish_exercise_media(
    source_path: Path,
    *,
    settings: Settings,
    namespace: str,
    extension: str | None = None,
) -> StoredExerciseMedia:
    """Publish validated media under a deterministic, content-addressed exercise path."""
    if not source_path.is_file():
        raise ExerciseMediaStorageError("Exercise media source is not a file")
    safe_namespace = _validate_namespace(namespace)
    normalized_extension = (extension or source_path.suffix).lower()
    if (
        not normalized_extension.startswith(".")
        or len(normalized_extension) == 1
        or "/" in normalized_extension
        or "\\" in normalized_extension
    ):
        raise ExerciseMediaStorageError("Exercise media extension is required")

    digest = sha256_file(source_path)
    relative_path = Path("exercises") / safe_namespace / f"media-{digest}{normalized_extension}"
    destination = settings.media_root / relative_path
    public_path = f"{settings.media_public_path.rstrip('/')}/{relative_path.as_posix()}"

    if destination.exists() or destination.is_symlink():
        _verify_existing_destination(destination, digest)
        return StoredExerciseMedia(
            public_path=public_path,
            absolute_path=destination,
            created=False,
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        dir=destination.parent,
        prefix=".exercise-media-",
    ) as staging_directory:
        staged_path = Path(staging_directory) / "payload"
        with staged_path.open("wb") as staged_file:
            with source_path.open("rb") as source_file:
                shutil.copyfileobj(source_file, staged_file)
        if sha256_file(staged_path) != digest:
            raise ExerciseMediaStorageError("Exercise media changed while being published")
        try:
            os.link(staged_path, destination)
        except FileExistsError:
            _verify_existing_destination(destination, digest)
            return StoredExerciseMedia(
                public_path=public_path,
                absolute_path=destination,
                created=False,
            )
        return StoredExerciseMedia(
            public_path=public_path,
            absolute_path=destination,
            created=True,
        )
