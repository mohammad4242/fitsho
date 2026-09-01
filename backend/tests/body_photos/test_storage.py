import struct
import zlib
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.datastructures import Headers
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.auth.models import User
from app.body_photos.enums import BodyPhotoCleanupReason, BodyPhotoPurpose, BodyPhotoView
from app.body_photos.models import BodyPhotoStorageCleanup
from app.body_photos.service import BodyPhotoService
from app.body_photos.storage import BodyPhotoStorage, BodyPhotoStorageError, StoredBodyPhoto
from app.config import Settings

ORIGIN = {"Origin": "http://localhost:5173"}


def _png(
    width: int = 320,
    height: int = 640,
    color: tuple[int, int, int] = (17, 34, 51),
) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload))
        )

    rows = []
    for y in range(height):
        row = bytearray()
        for x in range(width):
            delta = 32 if (x // 24 + y // 24) % 2 else 0
            row.extend(min(channel + delta, 255) for channel in color)
        rows.append(b"\x00" + bytes(row))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + chunk(b"IEND", b"")
    )


def _png_with_declared_dimensions(width: int, height: int) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        checksum = struct.pack(">I", zlib.crc32(kind + payload))
        return struct.pack(">I", len(payload)) + kind + payload + checksum

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00"))
        + chunk(b"IEND", b"")
    )


def _jpeg_with_exif() -> bytes:
    output = BytesIO()
    image = Image.new("RGB", (320, 640), color=(30, 60, 90))
    draw = ImageDraw.Draw(image)
    for y in range(0, 640, 32):
        draw.rectangle((0, y, 319, min(y + 15, 639)), fill=(90, 120, 150))
    exif = Image.Exif()
    exif[274] = 1
    exif[315] = "private source metadata"
    image.save(output, format="JPEG", exif=exif)
    return output.getvalue()


def _register_and_create(client: TestClient, email: str) -> str:
    assert (
        client.post(
            "/api/v1/auth/register",
            headers=ORIGIN,
            json={"email": email, "password": "long password"},
        ).status_code
        == 201
    )
    created = client.post(
        "/api/v1/body-photo-sessions",
        headers=ORIGIN,
        json={"purpose": "initial_plan"},
    )
    assert created.status_code == 201
    return str(created.json()["id"])


def _upload(
    client: TestClient,
    session_id: str,
    content: bytes,
    content_type: str,
    headers: dict[str, str] | None = None,
) -> object:
    return client.put(
        f"/api/v1/body-photo-sessions/{session_id}/photos/front",
        headers=headers or ORIGIN,
        files={"file": ("front.png", content, content_type)},
    )


def _stored_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [path for path in root.rglob("*") if path.is_file()]


@pytest.mark.parametrize(
    ("content", "content_type"),
    [
        (_png(), "image/jpeg"),
        (b"\x89PNG\r\n\x1a\nnot-a-real-image", "image/png"),
    ],
)
def test_mime_mismatch_and_corruption_leave_no_stored_file(
    client: TestClient,
    test_settings: Settings,
    content: bytes,
    content_type: str,
) -> None:
    private_root = Path(test_settings.media_root).parent / "body-private"
    test_settings.body_photo_storage_root = private_root
    session_id = _register_and_create(
        client, f"bad-image-{content_type.split('/')[-1]}@example.com"
    )

    response = _upload(client, session_id, content, content_type)

    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "invalid_image"}}
    assert _stored_files(private_root) == []


def test_excessive_bytes_and_pixels_leave_no_stored_file(
    client: TestClient,
    test_settings: Settings,
) -> None:
    private_root = Path(test_settings.media_root).parent / "body-private"
    test_settings.body_photo_storage_root = private_root
    session_id = _register_and_create(client, "photo-limits@example.com")

    test_settings.body_photo_max_bytes = 20
    too_many_bytes = _upload(client, session_id, _png(), "image/png")
    test_settings.body_photo_max_bytes = 1024 * 1024
    test_settings.body_photo_max_pixels = 16
    test_settings.body_photo_min_width = 1
    test_settings.body_photo_min_height = 1
    tiny_pixels = _png(5, 5)
    too_many_pixels = _upload(client, session_id, tiny_pixels, "image/png")

    assert too_many_bytes.status_code == 422
    assert too_many_pixels.status_code == 422
    assert _stored_files(private_root) == []


def test_pillow_decompression_bomb_warning_is_sanitized_and_stores_nothing(
    client: TestClient,
    test_settings: Settings,
) -> None:
    private_root = Path(test_settings.media_root).parent / "body-private"
    test_settings.body_photo_storage_root = private_root
    session_id = _register_and_create(client, "photo-bomb@example.com")

    bomb = _png_with_declared_dimensions(10_000, 10_000)
    response = _upload(client, session_id, bomb, "image/png")

    assert response.status_code == 422
    assert response.json() == {"detail": {"code": "image_too_large"}}
    assert _stored_files(private_root) == []


def test_landscape_geometry_is_rejected_without_storage(
    client: TestClient,
    test_settings: Settings,
) -> None:
    private_root = Path(test_settings.media_root).parent / "body-private"
    test_settings.body_photo_storage_root = private_root
    session_id = _register_and_create(client, "crop-geometry@example.com")

    landscape = _png(800, 400)
    response = _upload(client, session_id, landscape, "image/png")

    assert response.status_code == 422
    assert _stored_files(private_root) == []


@pytest.mark.parametrize(
    ("width", "height"),
    [(240, 640), (320, 480)],
)
def test_minimum_width_and_height_are_enforced_independently(
    client: TestClient,
    test_settings: Settings,
    width: int,
    height: int,
) -> None:
    private_root = Path(test_settings.media_root).parent / "body-private"
    test_settings.body_photo_storage_root = private_root
    session_id = _register_and_create(client, f"photo-tiny-{width}-{height}@example.com")
    tiny = _png(width, height)

    response = _upload(client, session_id, tiny, "image/png")

    assert response.status_code == 422
    assert _stored_files(private_root) == []


@pytest.mark.parametrize(
    ("setting_name", "configured_minimum"),
    [("body_photo_min_width", 400), ("body_photo_min_height", 700)],
)
def test_dimension_minimums_are_configurable(
    client: TestClient,
    test_settings: Settings,
    setting_name: str,
    configured_minimum: int,
) -> None:
    private_root = Path(test_settings.media_root).parent / "body-private"
    test_settings.body_photo_storage_root = private_root
    setattr(test_settings, setting_name, configured_minimum)
    session_id = _register_and_create(client, f"photo-config-{setting_name}@example.com")
    content = _png()

    response = _upload(client, session_id, content, "image/png")

    assert response.status_code == 422
    assert _stored_files(private_root) == []


def test_accepted_jpeg_is_reencoded_without_exif(
    client: TestClient,
    test_settings: Settings,
) -> None:
    private_root = Path(test_settings.media_root).parent / "body-private"
    test_settings.body_photo_storage_root = private_root
    session_id = _register_and_create(client, "photo-exif@example.com")

    jpeg = _jpeg_with_exif()
    uploaded = client.put(
        f"/api/v1/body-photo-sessions/{session_id}/photos/front",
        headers=ORIGIN,
        files={"file": ("front.jpg", jpeg, "image/jpeg")},
    )
    content = client.get(f"/api/v1/body-photo-sessions/{session_id}/photos/front/content")

    assert uploaded.status_code == 200
    assert content.status_code == 200
    with Image.open(BytesIO(content.content)) as normalized:
        assert normalized.format == "JPEG"
        assert len(normalized.getexif()) == 0


def test_private_storage_uses_generated_keys_outside_public_media(
    test_settings: Settings,
) -> None:
    private_root = Path(test_settings.media_root).parent / "body-private"
    test_settings.body_photo_storage_root = private_root
    storage = BodyPhotoStorage(test_settings)

    stored = storage.store(_png(), ".png")

    assert stored.key != "front.png"
    assert "/" in stored.key
    stored_path = private_root.joinpath(*stored.key.split("/"))
    assert stored_path.is_relative_to(private_root)
    assert not stored_path.is_relative_to(test_settings.media_root)
    assert storage.open(stored.key).read() == _png()
    storage.delete(stored.key)
    assert not stored_path.exists()


def test_service_accepts_storage_interface_injection(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    class MemoryStorage:
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {}

        def store(self, content: bytes, extension: str) -> StoredBodyPhoto:
            key = f"memory/photo{extension}"
            self.objects[key] = content
            return StoredBodyPhoto(key=key)

        def open(self, key: str) -> BytesIO:
            return BytesIO(self.objects[key])

        def delete(self, key: str) -> None:
            self.objects.pop(key, None)

    test_settings.body_photo_storage_root = (
        Path(test_settings.media_root).parent / "body-private-storage-port"
    )
    assert (
        client.post(
            "/api/v1/auth/register",
            headers=ORIGIN,
            json={"email": "photo-storage-port@example.com", "password": "long password"},
        ).status_code
        == 201
    )
    user = db.scalar(select(User).where(User.email == "photo-storage-port@example.com"))
    assert user is not None
    storage = MemoryStorage()
    service = BodyPhotoService(db, test_settings, storage=storage)
    session = service.create_session(user.id, BodyPhotoPurpose.INITIAL_PLAN)
    content = _png()
    upload = StarletteUploadFile(
        BytesIO(content),
        filename="front.png",
        headers=Headers({"content-type": "image/png"}),
    )

    updated = service.upload_standardized_photo(
        session.id,
        user.id,
        BodyPhotoView.FRONT,
        upload,
    )

    assert len(updated.photos) == 1
    assert updated.photos[0].storage_key in storage.objects
    assert _stored_files(test_settings.body_photo_storage_root) == []


def test_failed_db_commit_and_failed_delete_persist_cleanup_in_separate_session(
    client: TestClient,
    db: Session,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingDeleteStorage:
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {}

        def store(self, content: bytes, extension: str) -> StoredBodyPhoto:
            key = f"memory/uncommitted{extension}"
            self.objects[key] = content
            return StoredBodyPhoto(key=key)

        def open(self, key: str) -> BytesIO:
            return BytesIO(self.objects[key])

        def delete(self, key: str) -> None:
            raise BodyPhotoStorageError(f"cannot delete {key}")

    assert (
        client.post(
            "/api/v1/auth/register",
            headers=ORIGIN,
            json={"email": "photo-commit-cleanup@example.com", "password": "long password"},
        ).status_code
        == 201
    )
    user = db.scalar(select(User).where(User.email == "photo-commit-cleanup@example.com"))
    assert user is not None
    cleanup_sessions: list[Session] = []

    def cleanup_session_factory() -> Session:
        session = Session(bind=db.connection(), join_transaction_mode="create_savepoint")
        cleanup_sessions.append(session)
        return session

    storage = FailingDeleteStorage()
    service = BodyPhotoService(
        db,
        test_settings,
        storage=storage,
        cleanup_session_factory=cleanup_session_factory,
    )
    session = service.create_session(user.id, BodyPhotoPurpose.INITIAL_PLAN)
    original_commit = db.commit
    commit_calls = 0

    def fail_photo_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1
        if commit_calls == 2:
            raise SQLAlchemyError("forced photo commit failure")
        original_commit()

    monkeypatch.setattr(db, "commit", fail_photo_commit)
    content = _png()
    upload = StarletteUploadFile(
        BytesIO(content),
        filename="front.png",
        headers=Headers({"content-type": "image/png"}),
    )

    with pytest.raises(SQLAlchemyError, match="forced photo commit failure"):
        service.upload_standardized_photo(
            session.id,
            user.id,
            BodyPhotoView.FRONT,
            upload,
        )

    cleanup = db.scalar(select(BodyPhotoStorageCleanup))
    assert cleanup_sessions
    assert cleanup is not None
    assert cleanup.storage_key == "memory/uncommitted.png"
    assert cleanup.reason is BodyPhotoCleanupReason.FAILED_UPLOAD_ROLLBACK
    assert cleanup.storage_key in storage.objects


def test_replacement_retains_failed_cleanup_and_retries_it(
    client: TestClient,
    db: Session,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root = Path(test_settings.media_root).parent / "body-private"
    test_settings.body_photo_storage_root = private_root
    session_id = _register_and_create(client, "photo-replace-cleanup@example.com")
    assert _upload(client, session_id, _png(), "image/png").status_code == 200
    original_delete = BodyPhotoStorage.delete

    def unavailable_delete(_storage: BodyPhotoStorage, _key: str) -> None:
        raise BodyPhotoStorageError("unavailable")

    monkeypatch.setattr(BodyPhotoStorage, "delete", unavailable_delete)
    replacement_content = _png(color=(80, 70, 60))
    replacement = _upload(client, session_id, replacement_content, "image/png")

    assert replacement.status_code == 200
    assert db.scalar(text("SELECT count(*) FROM body_photo_storage_cleanups")) == 1
    assert len(_stored_files(private_root)) == 2

    monkeypatch.setattr(BodyPhotoStorage, "delete", original_delete)
    final_content = _png(color=(40, 30, 20))
    retried = _upload(client, session_id, final_content, "image/png")

    assert retried.status_code == 200
    assert db.scalar(text("SELECT count(*) FROM body_photo_storage_cleanups")) == 0
    assert len(_stored_files(private_root)) == 1


def test_delete_failure_is_retryable_without_losing_cleanup_key(
    client: TestClient,
    db: Session,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    private_root = Path(test_settings.media_root).parent / "body-private"
    test_settings.body_photo_storage_root = private_root
    session_id = _register_and_create(client, "photo-delete-cleanup@example.com")
    assert _upload(client, session_id, _png(), "image/png").status_code == 200
    original_delete = BodyPhotoStorage.delete

    def unavailable_delete(_storage: BodyPhotoStorage, _key: str) -> None:
        raise BodyPhotoStorageError("unavailable")

    monkeypatch.setattr(BodyPhotoStorage, "delete", unavailable_delete)
    first_delete = client.delete(
        f"/api/v1/body-photo-sessions/{session_id}",
        headers=ORIGIN,
    )

    assert first_delete.status_code == 503
    assert db.scalar(text("SELECT count(*) FROM body_photo_storage_cleanups")) == 1
    assert len(_stored_files(private_root)) == 1

    monkeypatch.setattr(BodyPhotoStorage, "delete", original_delete)
    retry = client.delete(
        f"/api/v1/body-photo-sessions/{session_id}",
        headers=ORIGIN,
    )

    assert retry.status_code == 204
    assert db.scalar(text("SELECT count(*) FROM body_photo_storage_cleanups")) == 0
    assert _stored_files(private_root) == []


def test_stored_body_photo_has_readable_permissions(
    test_settings: Settings, tmp_path: Path
) -> None:
    test_settings.body_photo_storage_root = tmp_path
    storage = BodyPhotoStorage(test_settings)
    stored = storage.store(b"dummy image data", ".jpg")
    stored_path = tmp_path / stored.key
    assert stored_path.is_file()
    mode = stored_path.stat().st_mode & 0o777
    assert mode == 0o644

