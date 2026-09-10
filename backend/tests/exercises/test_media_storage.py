import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from app.config import Settings
from app.exercises import media_storage
from app.exercises.media_storage import ExerciseMediaStorageError, publish_exercise_media

GIF_BYTES = b"GIF89a" + b"\x00" * 32


def storage_settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        cookie_secure=False,
        session_cookie_name="fitsho_session",
        media_root=tmp_path / "media",
    )


def test_identical_bytes_in_distinct_exercise_namespaces_are_not_shared(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.gif"
    source.write_bytes(GIF_BYTES)
    settings = storage_settings(tmp_path)

    first = publish_exercise_media(source, settings=settings, namespace="exercise-one")
    second = publish_exercise_media(source, settings=settings, namespace="exercise-two")

    assert first.absolute_path != second.absolute_path
    assert first.public_path == f"/media/exercises/exercise-one/{first.absolute_path.name}"
    assert second.public_path == f"/media/exercises/exercise-two/{second.absolute_path.name}"
    assert first.created is True
    assert second.created is True
    assert first.absolute_path.read_bytes() == GIF_BYTES
    assert second.absolute_path.read_bytes() == GIF_BYTES


@pytest.mark.parametrize(
    "namespace",
    ["", ".", "..", "../escape", "nested/exercise", "/absolute", "exercise\\child"],
)
def test_unsafe_exercise_namespace_is_rejected(tmp_path: Path, namespace: str) -> None:
    source = tmp_path / "source.gif"
    source.write_bytes(GIF_BYTES)

    with pytest.raises(ExerciseMediaStorageError, match="namespace"):
        publish_exercise_media(source, settings=storage_settings(tmp_path), namespace=namespace)


def test_existing_file_in_one_namespace_cannot_affect_another(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.gif"
    source.write_bytes(GIF_BYTES)
    settings = storage_settings(tmp_path)
    first = publish_exercise_media(source, settings=settings, namespace="exercise-one")
    first.absolute_path.write_bytes(b"corrupted existing file")

    second = publish_exercise_media(source, settings=settings, namespace="exercise-two")

    assert second.created is True
    assert second.absolute_path.read_bytes() == GIF_BYTES
    assert first.absolute_path.read_bytes() == b"corrupted existing file"


def test_video_poster_path_is_derived_beside_managed_video() -> None:
    derive_path = getattr(media_storage, "exercise_video_poster_path", None)

    assert callable(derive_path)
    assert derive_path("/media/exercises/bench/media-abc.mp4") == (
        "/media/exercises/bench/media-abc.poster.webp"
    )
    assert derive_path("/media/exercises/bench/media-abc.webm") == (
        "/media/exercises/bench/media-abc.poster.webp"
    )
    assert derive_path("https://cdn.example/video.mp4") is None
    assert derive_path("/media/exercises/bench/media-abc.gif") is None


def test_video_poster_is_generated_atomically_and_reused(tmp_path: Path) -> None:
    ensure_poster = getattr(media_storage, "ensure_exercise_video_poster", None)
    assert callable(ensure_poster)
    settings = storage_settings(tmp_path)
    video = settings.media_root / "exercises" / "bench" / "media-abc.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"video")
    commands: list[list[str]] = []

    def successful_runner(
        command: Sequence[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        rendered = list(command)
        commands.append(rendered)
        Path(rendered[-1]).write_bytes(b"RIFF\x00\x00\x00\x00WEBPVP8 ")
        return subprocess.CompletedProcess(rendered, 0, "", "")

    first = ensure_poster(
        "/media/exercises/bench/media-abc.mp4",
        settings=settings,
        runner=successful_runner,
    )
    second = ensure_poster(
        "/media/exercises/bench/media-abc.mp4",
        settings=settings,
        runner=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("existing poster must be reused")
        ),
    )

    assert first.public_path == "/media/exercises/bench/media-abc.poster.webp"
    assert first.absolute_path.read_bytes().startswith(b"RIFF")
    assert first.created is True
    assert second == first.__class__(
        public_path=first.public_path,
        absolute_path=first.absolute_path,
        created=False,
    )
    assert commands[0][0] == settings.ffmpeg_path
    assert "scale=" in " ".join(commands[0])


def test_video_poster_failure_keeps_source_and_cleans_staging(tmp_path: Path) -> None:
    ensure_poster = getattr(media_storage, "ensure_exercise_video_poster", None)
    assert callable(ensure_poster)
    settings = storage_settings(tmp_path)
    video = settings.media_root / "exercises" / "bench" / "media-abc.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"keep-video")

    def failed_runner(
        command: Sequence[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(list(command), 1, "", "failed")

    with pytest.raises(ExerciseMediaStorageError, match="poster"):
        ensure_poster(
            "/media/exercises/bench/media-abc.mp4",
            settings=settings,
            runner=failed_runner,
        )

    assert video.read_bytes() == b"keep-video"
    assert list(video.parent.glob(".poster-*")) == []


def test_video_poster_backfill_reuses_existing_and_isolates_failures(tmp_path: Path) -> None:
    backfill = getattr(media_storage, "backfill_exercise_video_posters", None)
    assert callable(backfill)
    settings = storage_settings(tmp_path)
    video_root = settings.media_root / "exercises"
    successful_video = video_root / "a" / "media-success.mp4"
    failed_video = video_root / "b" / "media-failed.webm"
    reused_video = video_root / "c" / "media-reused.mp4"
    for video in (successful_video, failed_video, reused_video):
        video.parent.mkdir(parents=True, exist_ok=True)
        video.write_bytes(b"video")
    reused_video.with_suffix(".poster.webp").write_bytes(b"RIFF\x00\x00\x00\x00WEBPVP8 ")

    def mixed_runner(
        command: Sequence[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        rendered = list(command)
        if "failed" in rendered[5]:
            return subprocess.CompletedProcess(rendered, 1, "", "failed")
        Path(rendered[-1]).write_bytes(b"RIFF\x00\x00\x00\x00WEBPVP8 ")
        return subprocess.CompletedProcess(rendered, 0, "", "")

    report = backfill(settings=settings, runner=mixed_runner)

    assert report.scanned == 3
    assert report.created == 1
    assert report.reused == 1
    assert report.failed == 1
    assert report.failures == ("/media/exercises/b/media-failed.webm",)
