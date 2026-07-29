from io import BytesIO
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.admin.media import MediaValidationError, discard_media, store_upload
from app.config import Settings
from app.exercises.enums import MediaType

GIF_BYTES = b"GIF89a" + b"\x00" * 32
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 32
MP4_BYTES = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 32
WEBM_BYTES = b"\x1a\x45\xdf\xa3" + b"\x00" * 32


def upload(filename: str, content: bytes, content_type: str) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def settings(
    tmp_path: Path,
    *,
    media_max_bytes: int = 20 * 1024 * 1024,
) -> Settings:
    return Settings(
        app_env="test",
        cookie_secure=False,
        session_cookie_name="fitsho_session",
        media_root=tmp_path,
        media_max_bytes=media_max_bytes,
    )


def test_valid_gif_is_stored_with_server_filename(tmp_path: Path) -> None:
    stored = store_upload(upload("demo.gif", GIF_BYTES, "image/gif"), settings(tmp_path))

    assert stored.media_type is MediaType.GIF
    assert stored.public_path.startswith("/media/")
    assert stored.absolute_path.parent == tmp_path
    assert stored.absolute_path.suffix == ".gif"
    assert stored.absolute_path.name != "demo.gif"
    assert stored.absolute_path.read_bytes() == GIF_BYTES


def test_valid_jpeg_thumbnail_is_stored_with_image_type(tmp_path: Path) -> None:
    stored = store_upload(upload("demo.jpg", JPEG_BYTES, "image/jpeg"), settings(tmp_path))

    assert stored.media_type is MediaType.IMAGE
    assert stored.absolute_path.suffix == ".jpg"
    assert stored.absolute_path.read_bytes() == JPEG_BYTES


@pytest.mark.parametrize(
    ("filename", "content", "content_type", "expected_type"),
    [
        ("demo.mp4", MP4_BYTES, "video/mp4", MediaType.VIDEO),
        ("demo.webm", WEBM_BYTES, "video/webm", MediaType.VIDEO),
    ],
)
def test_valid_short_video_is_stored(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    filename: str,
    content: bytes,
    content_type: str,
    expected_type: MediaType,
) -> None:
    monkeypatch.setattr("app.admin.media._probe_video_duration", lambda *_: 5.0)

    stored = store_upload(upload(filename, content, content_type), settings(tmp_path))

    assert stored.media_type is expected_type
    assert stored.absolute_path.suffix == Path(filename).suffix


@pytest.mark.parametrize(
    ("filename", "content", "content_type"),
    [
        ("payload.txt", b"hello", "text/plain"),
        ("payload.exe", b"MZ" + b"\x00" * 20, "application/octet-stream"),
        ("demo.mp4", MP4_BYTES, "video/webm"),
        ("demo.gif", MP4_BYTES, "image/gif"),
        ("demo.jpg", GIF_BYTES, "image/jpeg"),
    ],
)
def test_invalid_type_or_mismatched_signature_is_rejected(
    tmp_path: Path,
    filename: str,
    content: bytes,
    content_type: str,
) -> None:
    with pytest.raises(MediaValidationError):
        store_upload(upload(filename, content, content_type), settings(tmp_path))

    assert list(tmp_path.iterdir()) == []


def test_empty_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(MediaValidationError, match="empty"):
        store_upload(upload("empty.gif", b"", "image/gif"), settings(tmp_path))


def test_oversized_file_is_rejected_and_cleaned_up(tmp_path: Path) -> None:
    with pytest.raises(MediaValidationError, match="20 bytes"):
        store_upload(
            upload("large.gif", GIF_BYTES, "image/gif"),
            settings(tmp_path, media_max_bytes=20),
        )

    assert list(tmp_path.iterdir()) == []


def test_excessive_video_duration_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.admin.media._probe_video_duration", lambda *_: 20.01)

    with pytest.raises(MediaValidationError, match="20 seconds"):
        store_upload(upload("long.mp4", MP4_BYTES, "video/mp4"), settings(tmp_path))

    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("filename", ["../demo.gif", "folder/demo.gif", "folder\\demo.gif"])
def test_path_traversal_filename_is_rejected(tmp_path: Path, filename: str) -> None:
    with pytest.raises(MediaValidationError, match="filename"):
        store_upload(upload(filename, GIF_BYTES, "image/gif"), settings(tmp_path))

    assert list(tmp_path.iterdir()) == []


def test_filename_collision_never_overwrites_existing_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = UUID("00000000-0000-0000-0000-000000000001")
    second = UUID("00000000-0000-0000-0000-000000000002")
    existing = tmp_path / f"{first.hex}.gif"
    existing.write_bytes(b"keep me")
    values = iter([first, second])
    monkeypatch.setattr("app.admin.media.uuid4", lambda: next(values))

    stored = store_upload(upload("demo.gif", GIF_BYTES, "image/gif"), settings(tmp_path))

    assert existing.read_bytes() == b"keep me"
    assert stored.absolute_path.name == f"{second.hex}.gif"


def test_discard_media_removes_only_stored_file(tmp_path: Path) -> None:
    stored = store_upload(upload("demo.gif", GIF_BYTES, "image/gif"), settings(tmp_path))

    discard_media(stored)

    assert not stored.absolute_path.exists()
