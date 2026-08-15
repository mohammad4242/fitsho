import hashlib
import subprocess
from collections.abc import Sequence
from pathlib import Path

from app.config import Settings


def make_av_video(path: Path) -> bytes:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=15",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000",
            "-t",
            "1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path.read_bytes()


def owner_video_settings(
    test_settings: Settings,
    tmp_path: Path,
) -> Settings:
    return test_settings.model_copy(
        update={
            "media_root": tmp_path / "media",
            "owner_video_import_work_root": tmp_path / "work",
            "ffmpeg_timeout_seconds": 30.0,
        }
    )


def test_prepare_owner_video_removes_audio_and_preserves_original(
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    from app.exercises.owner_video_media import prepare_owner_video, probe_video

    source = tmp_path / "source.mp4"
    original = make_av_video(source)
    settings = owner_video_settings(test_settings, tmp_path)

    prepared = prepare_owner_video(source, settings=settings)

    assert source.read_bytes() == original
    assert prepared.source_id == hashlib.sha256(original).hexdigest()
    assert prepared.source_path == source
    assert prepared.duration_seconds > 0
    assert len(prepared.frame_paths) == 5
    assert all(path.read_bytes().startswith(b"\xff\xd8\xff") for path in prepared.frame_paths)
    muted_probe = probe_video(prepared.muted_path, settings=settings)
    assert muted_probe.video_streams == 1
    assert muted_probe.audio_streams == 0


def test_owner_video_source_limit_allows_25_megabyte_mp4(
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    from app.exercises.owner_video_media import _validate_source

    source = tmp_path / "large-source.mp4"
    with source.open("wb") as file_handle:
        file_handle.write(b"\x00\x00\x00\x18ftypisom")
        file_handle.truncate(25 * 1024 * 1024)

    _validate_source(source, test_settings)


def test_publish_owner_video_uses_stable_media_path_and_reuses_valid_file(
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    from app.exercises.owner_video_media import prepare_owner_video, publish_owner_video

    source = tmp_path / "source.mp4"
    original = make_av_video(source)
    settings = owner_video_settings(test_settings, tmp_path)
    prepared = prepare_owner_video(source, settings=settings)

    first = publish_owner_video(prepared, settings=settings)
    second = publish_owner_video(prepared, settings=settings)

    digest = hashlib.sha256(original).hexdigest()
    assert first.public_path == f"/media/owner-video/{digest[:2]}/{digest}.mp4"
    assert first.absolute_path.is_file()
    assert first.created is True
    assert second == first.__class__(
        public_path=first.public_path,
        absolute_path=first.absolute_path,
        created=False,
    )


def test_prepare_owner_video_falls_back_when_stream_copy_fails(
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    from app.exercises.owner_video_media import prepare_owner_video, probe_video

    source = tmp_path / "source.mp4"
    make_av_video(source)
    settings = owner_video_settings(test_settings, tmp_path)
    commands: list[list[str]] = []

    def fail_copy_runner(
        command: Sequence[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        rendered = list(command)
        commands.append(rendered)
        if rendered[0] == "ffmpeg" and "copy" in rendered:
            return subprocess.CompletedProcess(rendered, 1, "", "copy failed")
        return subprocess.run(rendered, **kwargs)  # type: ignore[arg-type]

    prepared = prepare_owner_video(source, settings=settings, runner=fail_copy_runner)

    assert any("copy" in command for command in commands)
    assert any("libx264" in command for command in commands)
    assert probe_video(prepared.muted_path, settings=settings).audio_streams == 0


def test_prepare_owner_video_cleans_staging_when_ffmpeg_fails(
    test_settings: Settings,
    tmp_path: Path,
) -> None:
    from app.exercises.owner_video_media import OwnerVideoMediaError, prepare_owner_video

    source = tmp_path / "source.mp4"
    original = make_av_video(source)
    settings = owner_video_settings(test_settings, tmp_path)

    def fail_ffmpeg_runner(
        command: Sequence[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        rendered = list(command)
        if rendered[0] == "ffmpeg":
            return subprocess.CompletedProcess(rendered, 1, "", "encode failed")
        return subprocess.run(rendered, **kwargs)  # type: ignore[arg-type]

    try:
        prepare_owner_video(source, settings=settings, runner=fail_ffmpeg_runner)
    except OwnerVideoMediaError as error:
        assert str(error) == "ffmpeg could not create a muted video"
    else:
        raise AssertionError("expected media preparation to fail")

    assert source.read_bytes() == original
    assert list(settings.owner_video_import_work_root.rglob(".muted-*.mp4")) == []
