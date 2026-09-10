from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import uuid4

from app.config import Settings


class ExerciseMediaStorageError(ValueError):
    """Raised when a deterministic exercise-media destination is unsafe to publish."""


@dataclass(frozen=True)
class StoredExerciseMedia:
    public_path: str
    absolute_path: Path
    created: bool


@dataclass(frozen=True)
class StoredExercisePoster:
    public_path: str
    absolute_path: Path
    created: bool


@dataclass(frozen=True)
class ExerciseVideoPosterBackfillReport:
    scanned: int
    created: int
    reused: int
    failed: int
    failures: tuple[str, ...]


PosterCommandRunner = Callable[..., subprocess.CompletedProcess[str]]
VIDEO_POSTER_EXTENSIONS = frozenset({".mp4", ".webm"})


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


def exercise_video_poster_path(media_path: str) -> str | None:
    """Return the deterministic poster path for a managed exercise video."""
    if not media_path.startswith("/media/exercises/"):
        return None
    relative_path = media_path.removeprefix("/media/")
    path = PurePosixPath(relative_path)
    if (
        path.is_absolute()
        or ".." in path.parts
        or path.suffix.lower() not in VIDEO_POSTER_EXTENSIONS
    ):
        return None
    return f"/media/{path.with_suffix('.poster.webp').as_posix()}"


def _is_valid_webp(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        header = path.read_bytes()[:12]
    except OSError:
        return False
    return len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP"


def ensure_exercise_video_poster(
    media_path: str,
    *,
    settings: Settings,
    runner: PosterCommandRunner = subprocess.run,
) -> StoredExercisePoster:
    """Create a bounded WebP poster beside a managed exercise video without overwriting files."""
    public_path = exercise_video_poster_path(media_path)
    if public_path is None:
        raise ExerciseMediaStorageError("Exercise video poster requires managed video media")

    public_root = f"{settings.media_public_path.rstrip('/')}/"
    if not media_path.startswith(public_root) or not public_path.startswith(public_root):
        raise ExerciseMediaStorageError("Exercise video poster path does not match media settings")
    media_root = settings.media_root.resolve()
    video_path = (media_root / media_path.removeprefix(public_root)).resolve()
    poster_path = (media_root / public_path.removeprefix(public_root)).resolve()
    if media_root not in video_path.parents or media_root not in poster_path.parents:
        raise ExerciseMediaStorageError("Exercise video poster path escapes media storage")
    if not video_path.is_file():
        raise ExerciseMediaStorageError("Exercise video source is not a file")
    if poster_path.exists() or poster_path.is_symlink():
        if not _is_valid_webp(poster_path):
            raise ExerciseMediaStorageError("Existing exercise video poster is invalid")
        return StoredExercisePoster(public_path, poster_path, False)

    poster_path.parent.mkdir(parents=True, exist_ok=True)
    staged_path = poster_path.parent / f".poster-{uuid4().hex}.webp"
    try:
        try:
            result = runner(
                [
                    settings.ffmpeg_path,
                    "-y",
                    "-ss",
                    "0.100",
                    "-i",
                    str(video_path),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=min(640\\,iw):-2",
                    "-an",
                    "-c:v",
                    "libwebp",
                    "-quality",
                    "78",
                    "-compression_level",
                    "4",
                    str(staged_path),
                ],
                capture_output=True,
                text=True,
                timeout=settings.ffmpeg_timeout_seconds,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as error:
            raise ExerciseMediaStorageError(
                "Exercise video poster generation is unavailable"
            ) from error
        if result.returncode != 0 or not _is_valid_webp(staged_path):
            raise ExerciseMediaStorageError("Exercise video poster generation failed")
        try:
            os.link(staged_path, poster_path)
        except FileExistsError as error:
            if not _is_valid_webp(poster_path):
                raise ExerciseMediaStorageError(
                    "Existing exercise video poster is invalid"
                ) from error
            return StoredExercisePoster(public_path, poster_path, False)
        return StoredExercisePoster(public_path, poster_path, True)
    finally:
        staged_path.unlink(missing_ok=True)


def backfill_exercise_video_posters(
    *,
    settings: Settings,
    runner: PosterCommandRunner = subprocess.run,
) -> ExerciseVideoPosterBackfillReport:
    """Create missing posters for every managed exercise video and isolate bad files."""
    exercise_root = settings.media_root / "exercises"
    video_paths = sorted(
        path
        for path in exercise_root.rglob("*")
        if path.is_file() and path.suffix.lower() in VIDEO_POSTER_EXTENSIONS
    ) if exercise_root.is_dir() else []
    created = 0
    reused = 0
    failures: list[str] = []
    public_root = settings.media_public_path.rstrip("/")
    for video_path in video_paths:
        relative_path = video_path.relative_to(settings.media_root).as_posix()
        public_path = f"{public_root}/{relative_path}"
        try:
            result = ensure_exercise_video_poster(
                public_path,
                settings=settings,
                runner=runner,
            )
        except ExerciseMediaStorageError:
            failures.append(public_path)
            continue
        if result.created:
            created += 1
        else:
            reused += 1
    return ExerciseVideoPosterBackfillReport(
        scanned=len(video_paths),
        created=created,
        reused=reused,
        failed=len(failures),
        failures=tuple(failures),
    )


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
