import hashlib
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.admin import media
from app.admin.media import MediaValidationError, discard_media, store_upload
from app.config import Settings
from app.exercises.enums import MediaType

GIF_BYTES = b"GIF89a" + b"\x00" * 32
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"\x00" * 32
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
MP4_BYTES = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 32
WEBM_BYTES = b"\x1a\x45\xdf\xa3" + b"\x00" * 32
WEBP_BYTES = b"RIFF\x20\x00\x00\x00WEBP" + b"\x00" * 32


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
    active_settings = settings(tmp_path)
    stored = store_upload(
        upload("demo.gif", GIF_BYTES, "image/gif"), active_settings, "test-exercise"
    )
    digest = hashlib.sha256(GIF_BYTES).hexdigest()

    assert stored.media_type is MediaType.GIF
    assert stored.public_path == f"/media/exercises/test-exercise/media-{digest}.gif"
    assert stored.absolute_path.parent == tmp_path / "exercises" / "test-exercise"
    assert stored.absolute_path.suffix == ".gif"
    assert stored.absolute_path.name != "demo.gif"
    assert stored.absolute_path.read_bytes() == GIF_BYTES


def test_identical_exercise_upload_reuses_verified_destination(tmp_path: Path) -> None:
    active_settings = settings(tmp_path)

    first = store_upload(
        upload("demo.gif", GIF_BYTES, "image/gif"), active_settings, "test-exercise"
    )
    second = store_upload(
        upload("renamed.gif", GIF_BYTES, "image/gif"), active_settings, "test-exercise"
    )

    assert second.absolute_path == first.absolute_path
    assert second.public_path == first.public_path
    assert first.created is True
    assert second.created is False
    assert len(list((tmp_path / "exercises").rglob("*.gif"))) == 1


def test_exercise_upload_rejects_mismatching_existing_destination_without_overwrite(
    tmp_path: Path,
) -> None:
    digest = hashlib.sha256(GIF_BYTES).hexdigest()
    destination = tmp_path / "exercises" / "test-exercise" / f"media-{digest}.gif"
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"keep this unrelated file")

    with pytest.raises(MediaValidationError, match="does not match"):
        store_upload(
            upload("demo.gif", GIF_BYTES, "image/gif"), settings(tmp_path), "test-exercise"
        )

    assert destination.read_bytes() == b"keep this unrelated file"


def test_valid_jpeg_thumbnail_is_stored_with_image_type(tmp_path: Path) -> None:
    stored = store_upload(
        upload("demo.jpeg", JPEG_BYTES, "image/jpeg"), settings(tmp_path), "test-exercise"
    )
    digest = hashlib.sha256(JPEG_BYTES).hexdigest()

    assert stored.media_type is MediaType.IMAGE
    assert stored.public_path == f"/media/exercises/test-exercise/media-{digest}.jpeg"
    assert stored.absolute_path.suffix == ".jpeg"
    assert stored.absolute_path.read_bytes() == JPEG_BYTES


@pytest.mark.parametrize(
    ("filename", "content", "content_type", "suffix"),
    [
        ("food.png", PNG_BYTES, "image/png", ".png"),
        ("food.webp", WEBP_BYTES, "image/webp", ".webp"),
        ("food.jpg", JPEG_BYTES, "image/jpeg", ".jpg"),
    ],
)
def test_food_image_is_stored_in_scoped_public_directory(
    tmp_path: Path,
    filename: str,
    content: bytes,
    content_type: str,
    suffix: str,
) -> None:
    stored = media.store_image_upload(
        upload(filename, content, content_type),
        settings(tmp_path),
        "food-catalogue",
    )

    assert stored.media_type is MediaType.IMAGE
    assert stored.public_path.startswith("/media/food-catalogue/")
    assert stored.absolute_path.parent == tmp_path / "food-catalogue"
    assert stored.absolute_path.suffix == suffix
    assert stored.absolute_path.read_bytes() == content


def test_food_image_upload_rejects_non_image_media(tmp_path: Path) -> None:
    with pytest.raises(MediaValidationError, match="image"):
        media.store_image_upload(
            upload("food.mp4", MP4_BYTES, "video/mp4"),
            settings(tmp_path),
            "food-catalogue",
        )


@pytest.mark.parametrize("subdirectory", ["../food-catalogue", "nested/food", "food\\image"])
def test_food_image_upload_rejects_unsafe_subdirectory(tmp_path: Path, subdirectory: str) -> None:
    with pytest.raises(MediaValidationError, match="directory"):
        media.store_image_upload(
            upload("food.png", PNG_BYTES, "image/png"),
            settings(tmp_path),
            subdirectory,
        )


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

    stored = store_upload(
        upload(filename, content, content_type), settings(tmp_path), "test-exercise"
    )

    assert stored.media_type is expected_type
    assert stored.absolute_path.suffix == Path(filename).suffix


def test_video_upload_allows_up_to_64_mebibytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.admin.media._probe_video_duration", lambda *_: 5.0)
    content = MP4_BYTES + b"\x00" * (64 * 1024 * 1024 - len(MP4_BYTES))

    stored = store_upload(
        upload("large.mp4", content, "video/mp4"), settings(tmp_path), "test-exercise"
    )

    assert stored.media_type is MediaType.VIDEO
    assert stored.absolute_path.stat().st_size == 64 * 1024 * 1024


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
        store_upload(
            upload(filename, content, content_type), settings(tmp_path), "test-exercise"
        )

    assert list(tmp_path.iterdir()) == []


def test_empty_file_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(MediaValidationError, match="empty"):
        store_upload(
            upload("empty.gif", b"", "image/gif"), settings(tmp_path), "test-exercise"
        )


def test_oversized_file_is_rejected_and_cleaned_up(tmp_path: Path) -> None:
    with pytest.raises(MediaValidationError, match="20 bytes"):
        store_upload(
            upload("large.gif", GIF_BYTES, "image/gif"),
            settings(tmp_path, media_max_bytes=20),
            "test-exercise",
        )

    assert list(tmp_path.iterdir()) == []


def test_excessive_video_duration_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.admin.media._probe_video_duration", lambda *_: 20.01)

    with pytest.raises(MediaValidationError, match="20 seconds"):
        store_upload(
            upload("long.mp4", MP4_BYTES, "video/mp4"), settings(tmp_path), "test-exercise"
        )

    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("filename", ["../demo.gif", "folder/demo.gif", "folder\\demo.gif"])
def test_path_traversal_filename_is_rejected(tmp_path: Path, filename: str) -> None:
    with pytest.raises(MediaValidationError, match="filename"):
        store_upload(
            upload(filename, GIF_BYTES, "image/gif"), settings(tmp_path), "test-exercise"
        )

    assert list(tmp_path.iterdir()) == []


def test_unrelated_existing_file_is_never_overwritten(tmp_path: Path) -> None:
    existing = tmp_path / "legacy.gif"
    existing.write_bytes(b"keep me")

    stored = store_upload(
        upload("demo.gif", GIF_BYTES, "image/gif"), settings(tmp_path), "test-exercise"
    )

    assert existing.read_bytes() == b"keep me"
    assert stored.absolute_path.name != existing.name


def test_discard_media_removes_only_stored_file(tmp_path: Path) -> None:
    stored = store_upload(
        upload("demo.gif", GIF_BYTES, "image/gif"), settings(tmp_path), "test-exercise"
    )

    discard_media(stored)

    assert not stored.absolute_path.exists()
