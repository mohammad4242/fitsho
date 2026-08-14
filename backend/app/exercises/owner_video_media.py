from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.admin.media import _signature_extension
from app.config import Settings

CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
FRAME_POSITIONS = (0.10, 0.30, 0.50, 0.70, 0.90)


class OwnerVideoMediaError(ValueError):
    pass


@dataclass(frozen=True)
class VideoProbe:
    duration_seconds: float
    video_streams: int
    audio_streams: int


@dataclass(frozen=True)
class PreparedOwnerVideo:
    source_path: Path
    source_id: str
    muted_path: Path
    frame_paths: tuple[Path, ...]
    duration_seconds: float


@dataclass(frozen=True)
class PublishedOwnerVideo:
    public_path: str
    absolute_path: Path
    created: bool


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        while chunk := file_handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _run(
    command: Sequence[str],
    *,
    timeout: float,
    runner: CommandRunner,
) -> subprocess.CompletedProcess[str]:
    try:
        return runner(
            list(command),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as error:
        raise OwnerVideoMediaError(f"Media command is unavailable: {command[0]}") from error
    except subprocess.TimeoutExpired as error:
        raise OwnerVideoMediaError(f"Media command timed out: {command[0]}") from error


def probe_video(
    path: Path,
    *,
    settings: Settings,
    runner: CommandRunner = subprocess.run,
) -> VideoProbe:
    result = _run(
        [
            settings.ffprobe_path,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        timeout=settings.ffprobe_timeout_seconds,
        runner=runner,
    )
    if result.returncode != 0:
        raise OwnerVideoMediaError("Video file could not be validated")
    try:
        payload = json.loads(result.stdout)
        streams = payload["streams"]
        duration_seconds = float(payload["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise OwnerVideoMediaError("Video probe returned invalid metadata") from error
    if not isinstance(streams, list):
        raise OwnerVideoMediaError("Video probe returned invalid streams")
    video_streams = sum(
        1 for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "video"
    )
    audio_streams = sum(
        1 for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "audio"
    )
    if duration_seconds <= 0:
        raise OwnerVideoMediaError("Video duration must be positive")
    if video_streams < 1:
        raise OwnerVideoMediaError("Video stream is required")
    return VideoProbe(
        duration_seconds=duration_seconds,
        video_streams=video_streams,
        audio_streams=audio_streams,
    )


def _validate_source(path: Path, settings: Settings) -> None:
    if not path.is_file() or path.suffix.lower() != ".mp4":
        raise OwnerVideoMediaError("Source must be an MP4 file")
    size = path.stat().st_size
    if size == 0:
        raise OwnerVideoMediaError("Source video cannot be empty")
    if size > settings.import_media_max_bytes:
        raise OwnerVideoMediaError(
            f"Source video exceeds the {settings.import_media_max_bytes} bytes limit"
        )
    with path.open("rb") as file_handle:
        if _signature_extension(file_handle.read(64)) != ".mp4":
            raise OwnerVideoMediaError("Source signature is not MP4")


def _muted_video_is_valid(path: Path, settings: Settings, runner: CommandRunner) -> VideoProbe:
    probe = probe_video(path, settings=settings, runner=runner)
    if probe.audio_streams != 0:
        raise OwnerVideoMediaError("Muted video still contains audio")
    return probe


def _create_muted_video(
    source_path: Path,
    destination: Path,
    *,
    settings: Settings,
    runner: CommandRunner,
) -> VideoProbe:
    staged_path = destination.parent / f".muted-{uuid4().hex}.mp4"
    try:
        copy_result = _run(
            [
                settings.ffmpeg_path,
                "-y",
                "-i",
                str(source_path),
                "-map",
                "0:v:0",
                "-c:v",
                "copy",
                "-an",
                "-movflags",
                "+faststart",
                str(staged_path),
            ],
            timeout=settings.ffmpeg_timeout_seconds,
            runner=runner,
        )
        if copy_result.returncode != 0:
            staged_path.unlink(missing_ok=True)
            encode_result = _run(
                [
                    settings.ffmpeg_path,
                    "-y",
                    "-i",
                    str(source_path),
                    "-map",
                    "0:v:0",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    "18",
                    "-pix_fmt",
                    "yuv420p",
                    "-an",
                    "-movflags",
                    "+faststart",
                    str(staged_path),
                ],
                timeout=settings.ffmpeg_timeout_seconds,
                runner=runner,
            )
            if encode_result.returncode != 0:
                raise OwnerVideoMediaError("ffmpeg could not create a muted video")
        probe = _muted_video_is_valid(staged_path, settings, runner)
        os.replace(staged_path, destination)
        return probe
    finally:
        staged_path.unlink(missing_ok=True)


def _frame_is_valid(path: Path) -> bool:
    if not path.is_file():
        return False
    with path.open("rb") as file_handle:
        return _signature_extension(file_handle.read(64)) == ".jpg"


def _extract_frame(
    muted_path: Path,
    destination: Path,
    timestamp: float,
    *,
    settings: Settings,
    runner: CommandRunner,
) -> None:
    staged_path = destination.parent / f".frame-{uuid4().hex}.jpg"
    try:
        result = _run(
            [
                settings.ffmpeg_path,
                "-y",
                "-ss",
                f"{timestamp:.6f}",
                "-i",
                str(muted_path),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(staged_path),
            ],
            timeout=settings.ffmpeg_timeout_seconds,
            runner=runner,
        )
        if result.returncode != 0 or not _frame_is_valid(staged_path):
            raise OwnerVideoMediaError("ffmpeg could not extract a representative frame")
        os.replace(staged_path, destination)
    finally:
        staged_path.unlink(missing_ok=True)


def prepare_owner_video(
    source_path: Path,
    *,
    settings: Settings,
    runner: CommandRunner = subprocess.run,
) -> PreparedOwnerVideo:
    source_path = source_path.resolve()
    _validate_source(source_path, settings)
    source_probe = probe_video(source_path, settings=settings, runner=runner)
    source_id = sha256_file(source_path)
    work_directory = settings.owner_video_import_work_root / source_id
    work_directory.mkdir(parents=True, exist_ok=True)
    muted_path = work_directory / "muted.mp4"
    try:
        muted_probe = _muted_video_is_valid(muted_path, settings, runner)
    except OwnerVideoMediaError:
        muted_probe = _create_muted_video(
            source_path,
            muted_path,
            settings=settings,
            runner=runner,
        )

    frame_paths = tuple(
        work_directory / f"frame-{index:02d}.jpg"
        for index in range(1, len(FRAME_POSITIONS) + 1)
    )
    for frame_path, position in zip(frame_paths, FRAME_POSITIONS, strict=True):
        if not _frame_is_valid(frame_path):
            _extract_frame(
                muted_path,
                frame_path,
                source_probe.duration_seconds * position,
                settings=settings,
                runner=runner,
            )
    return PreparedOwnerVideo(
        source_path=source_path,
        source_id=source_id,
        muted_path=muted_path,
        frame_paths=frame_paths,
        duration_seconds=muted_probe.duration_seconds,
    )


def publish_owner_video(
    prepared: PreparedOwnerVideo,
    *,
    settings: Settings,
    runner: CommandRunner = subprocess.run,
) -> PublishedOwnerVideo:
    relative_path = (
        Path("owner-video")
        / prepared.source_id[:2]
        / f"{prepared.source_id}.mp4"
    )
    destination = settings.media_root / relative_path
    public_path = f"{settings.media_public_path.rstrip('/')}/{relative_path.as_posix()}"
    if destination.is_file():
        try:
            _muted_video_is_valid(destination, settings, runner)
        except OwnerVideoMediaError:
            pass
        else:
            return PublishedOwnerVideo(
                public_path=public_path,
                absolute_path=destination,
                created=False,
            )

    destination.parent.mkdir(parents=True, exist_ok=True)
    staged_path = destination.parent / f".publish-{uuid4().hex}.mp4"
    try:
        shutil.copyfile(prepared.muted_path, staged_path)
        _muted_video_is_valid(staged_path, settings, runner)
        os.replace(staged_path, destination)
    finally:
        staged_path.unlink(missing_ok=True)
    return PublishedOwnerVideo(
        public_path=public_path,
        absolute_path=destination,
        created=True,
    )
