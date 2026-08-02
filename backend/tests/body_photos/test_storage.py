import hashlib
import struct
import zlib
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from starlette.datastructures import Headers
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.auth.models import User
from app.body_photos.enums import BodyPhotoPurpose, BodyPhotoView
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

    rows = b"".join(b"\x00" + bytes(color) * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def _crop_headers(
    content: bytes,
    *,
    output_height: int = 640,
    original_height: int = 800,
    crop_top: int = 160,
    crop_bottom: int | None = None,
) -> dict[str, str]:
    bottom = crop_bottom if crop_bottom is not None else crop_top + output_height
    processed_sha256 = hashlib.sha256(content).hexdigest()
    evidence = f"v1:{processed_sha256}:{original_height}:{crop_top}:{bottom}"
    return {
        **ORIGIN,
        "X-Fitsho-Head-Cropped": "true",
        "X-Fitsho-Crop-Confidence": "0.95",
        "X-Fitsho-Original-Height": str(original_height),
        "X-Fitsho-Crop-Top": str(crop_top),
        "X-Fitsho-Crop-Bottom": str(bottom),
        "X-Fitsho-Processed-SHA256": processed_sha256,
        "X-Fitsho-Crop-Evidence-SHA256": hashlib.sha256(evidence.encode()).hexdigest(),
    }


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
        headers=headers or _crop_headers(content),
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
    assert response.json() == {"detail": "Body photo could not be accepted"}
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
    too_many_pixels = _upload(
        client,
        session_id,
        tiny_pixels,
        "image/png",
        _crop_headers(tiny_pixels, output_height=5, original_height=10, crop_top=5),
    )

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
    response = _upload(
        client,
        session_id,
        bomb,
        "image/png",
        _crop_headers(
            bomb,
            output_height=10_000,
            original_height=12_000,
            crop_top=2_000,
        ),
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Body photo could not be accepted"}
    assert _stored_files(private_root) == []


@pytest.mark.parametrize(
    "headers",
    [
        ORIGIN,
        {**_crop_headers(_png()), "X-Fitsho-Head-Cropped": "false"},
        {key: value for key, value in _crop_headers(_png()).items() if key != "X-Fitsho-Crop-Top"},
        {**_crop_headers(_png()), "X-Fitsho-Crop-Confidence": "0.2"},
    ],
)
def test_missing_or_unreliable_crop_attestation_is_rejected_without_storage(
    client: TestClient,
    test_settings: Settings,
    headers: dict[str, str],
) -> None:
    private_root = Path(test_settings.media_root).parent / "body-private"
    test_settings.body_photo_storage_root = private_root
    session_id = _register_and_create(client, f"crop-{len(headers)}@example.com")

    response = _upload(client, session_id, _png(), "image/png", headers)

    assert response.status_code == 422
    assert _stored_files(private_root) == []


def test_landscape_geometry_is_rejected_without_storage(
    client: TestClient,
    test_settings: Settings,
) -> None:
    private_root = Path(test_settings.media_root).parent / "body-private"
    test_settings.body_photo_storage_root = private_root
    session_id = _register_and_create(client, "crop-geometry@example.com")

    landscape = _png(800, 400)
    response = _upload(
        client,
        session_id,
        landscape,
        "image/png",
        _crop_headers(landscape, output_height=400, original_height=560, crop_top=160),
    )

    assert response.status_code == 422
    assert _stored_files(private_root) == []


@pytest.mark.parametrize(
    "header_overrides",
    [
        {"X-Fitsho-Processed-SHA256": "0" * 64},
        {"X-Fitsho-Crop-Evidence-SHA256": "0" * 64},
        {"X-Fitsho-Crop-Top": "20", "X-Fitsho-Crop-Bottom": "660"},
        {"X-Fitsho-Crop-Bottom": "799"},
        {"X-Fitsho-Original-Height": "not-an-integer"},
    ],
)
def test_unbound_or_unsafe_crop_geometry_is_rejected(
    client: TestClient,
    test_settings: Settings,
    header_overrides: dict[str, str],
) -> None:
    private_root = Path(test_settings.media_root).parent / "body-private"
    test_settings.body_photo_storage_root = private_root
    session_id = _register_and_create(client, f"crop-evidence-{len(header_overrides)}@example.com")
    content = _png()

    response = _upload(
        client,
        session_id,
        content,
        "image/png",
        {**_crop_headers(content), **header_overrides},
    )

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

    response = _upload(
        client,
        session_id,
        tiny,
        "image/png",
        _crop_headers(
            tiny,
            output_height=height,
            original_height=height + 160,
            crop_top=160,
        ),
    )

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


def test_crop_top_safety_threshold_is_configurable(
    client: TestClient,
    test_settings: Settings,
) -> None:
    private_root = Path(test_settings.media_root).parent / "body-private"
    test_settings.body_photo_storage_root = private_root
    test_settings.body_photo_min_crop_top_ratio = 0.25
    session_id = _register_and_create(client, "photo-crop-threshold@example.com")
    content = _png()

    response = _upload(client, session_id, content, "image/png")

    assert response.status_code == 422
    assert _stored_files(private_root) == []


def test_verified_crop_evidence_is_recorded_but_digest_is_not_exposed(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    private_root = Path(test_settings.media_root).parent / "body-private"
    test_settings.body_photo_storage_root = private_root
    session_id = _register_and_create(client, "photo-crop-record@example.com")
    content = _png()
    headers = _crop_headers(content)

    response = _upload(client, session_id, content, "image/png", headers)

    assert response.status_code == 200
    assert response.json()["photos"][0]["crop_geometry_verified"] is True
    assert "processed_sha256" not in response.text
    stored = db.execute(
        text(
            "SELECT crop_original_height, crop_top, crop_bottom, processed_sha256, "
            "crop_evidence_sha256 FROM body_photos"
        )
    ).one()
    assert stored == (
        800,
        160,
        800,
        headers["X-Fitsho-Processed-SHA256"],
        headers["X-Fitsho-Crop-Evidence-SHA256"],
    )


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
        headers=_crop_headers(jpeg),
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
    headers = _crop_headers(content)
    upload = StarletteUploadFile(
        BytesIO(content),
        filename="front.png",
        headers=Headers({"content-type": "image/png"}),
    )

    updated = service.upload_processed_photo(
        session.id,
        user.id,
        BodyPhotoView.FRONT,
        upload,
        head_cropped=headers["X-Fitsho-Head-Cropped"],
        crop_confidence=headers["X-Fitsho-Crop-Confidence"],
        original_height=headers["X-Fitsho-Original-Height"],
        crop_top=headers["X-Fitsho-Crop-Top"],
        crop_bottom=headers["X-Fitsho-Crop-Bottom"],
        processed_sha256=headers["X-Fitsho-Processed-SHA256"],
        crop_evidence_sha256=headers["X-Fitsho-Crop-Evidence-SHA256"],
    )

    assert len(updated.photos) == 1
    assert updated.photos[0].storage_key in storage.objects
    assert _stored_files(test_settings.body_photo_storage_root) == []


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
