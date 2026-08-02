import struct
import zlib
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings

ORIGIN = {"Origin": "http://localhost:5173"}
VALID_HEADERS = {
    **ORIGIN,
    "X-Fitsho-Head-Cropped": "true",
    "X-Fitsho-Crop-Confidence": "0.95",
}


def _png(width: int = 4, height: int = 8) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload))
        )

    rows = b"".join(b"\x00" + b"\x11\x22\x33" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
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
    image = Image.new("RGB", (4, 8), color=(30, 60, 90))
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
        headers=headers or VALID_HEADERS,
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
    too_many_pixels = _upload(client, session_id, _png(5, 5), "image/png")

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

    response = _upload(
        client,
        session_id,
        _png_with_declared_dimensions(10_000, 10_000),
        "image/png",
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Body photo could not be accepted"}
    assert _stored_files(private_root) == []


@pytest.mark.parametrize(
    "headers",
    [
        ORIGIN,
        {**ORIGIN, "X-Fitsho-Head-Cropped": "false", "X-Fitsho-Crop-Confidence": "0.95"},
        {**ORIGIN, "X-Fitsho-Head-Cropped": "true"},
        {**ORIGIN, "X-Fitsho-Head-Cropped": "true", "X-Fitsho-Crop-Confidence": "0.2"},
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

    response = _upload(client, session_id, _png(8, 4), "image/png")

    assert response.status_code == 422
    assert _stored_files(private_root) == []


def test_accepted_jpeg_is_reencoded_without_exif(
    client: TestClient,
    test_settings: Settings,
) -> None:
    private_root = Path(test_settings.media_root).parent / "body-private"
    test_settings.body_photo_storage_root = private_root
    session_id = _register_and_create(client, "photo-exif@example.com")

    uploaded = client.put(
        f"/api/v1/body-photo-sessions/{session_id}/photos/front",
        headers=VALID_HEADERS,
        files={"file": ("front.jpg", _jpeg_with_exif(), "image/jpeg")},
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
    from app.body_photos.storage import BodyPhotoStorage

    private_root = Path(test_settings.media_root).parent / "body-private"
    test_settings.body_photo_storage_root = private_root
    storage = BodyPhotoStorage(test_settings)

    stored = storage.store(_png(), ".png")

    assert stored.key != "front.png"
    assert "/" in stored.key
    assert stored.path.is_relative_to(private_root)
    assert not stored.path.is_relative_to(test_settings.media_root)
    assert storage.open(stored.key).read() == _png()
    storage.delete(stored.key)
    assert not stored.path.exists()
