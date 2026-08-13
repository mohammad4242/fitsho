import struct
import zlib
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.body_analysis.enums import BodyAnalysisStatus
from app.body_analysis.models import BodyAnalysis
from app.body_photos.enums import BodyPhotoSessionState
from app.body_photos.models import BodyPhotoSession
from app.config import Settings

ORIGIN = {"Origin": "http://localhost:5173"}


def _png(
    width: int = 320,
    height: int = 640,
    color: tuple[int, int, int] = (20, 40, 60),
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
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + chunk(b"IEND", b"")
    )


def _register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201


def _login(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 200


def _logout(client: TestClient) -> None:
    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204


def _create_session(client: TestClient, purpose: str = "initial_plan") -> dict[str, object]:
    response = client.post(
        "/api/v1/body-photo-sessions",
        headers=ORIGIN,
        json={"purpose": purpose},
    )
    assert response.status_code == 201
    return response.json()


def _upload(
    client: TestClient,
    session_id: object,
    view: str,
    content: bytes | None = None,
    *,
    headers: dict[str, str] | None = None,
    content_type: str = "image/png",
) -> object:
    payload = content or _png()
    return client.put(
        f"/api/v1/body-photo-sessions/{session_id}/photos/{view}",
        headers=headers or ORIGIN,
        files={"file": (f"{view}.png", payload, content_type)},
    )


def _consents(training_granted: bool = False) -> dict[str, object]:
    return {
        "operational_processing": {"granted": True, "version": "operational-v1"},
        "model_training": {"granted": training_granted, "version": "training-v1"},
    }


def test_photo_validation_failure_allows_replacing_only_the_rejected_view(
    client: TestClient,
    db: Session,
) -> None:
    _register(client, "photo-replace-rejected-view@example.com")
    created = _create_session(client)
    session_id = created["id"]
    for view in ("front", "side", "back"):
        assert _upload(client, session_id, view).status_code == 200

    session = db.get(BodyPhotoSession, UUID(str(session_id)))
    assert session is not None
    session.state = BodyPhotoSessionState.FAILED
    db.commit()

    response = _upload(client, session_id, "side", _png(color=(80, 70, 60)))

    assert response.status_code == 200
    payload = response.json()
    assert payload["state"] == "uploaded"
    assert [photo["view"] for photo in payload["photos"]] == ["back", "front", "side"]


def test_queued_session_with_a_failed_analysis_allows_replacing_a_rejected_view(
    client: TestClient,
    db: Session,
) -> None:
    _register(client, "photo-replace-queued-view@example.com")
    created = _create_session(client)
    session_id = created["id"]
    for view in ("front", "side", "back"):
        assert _upload(client, session_id, view).status_code == 200

    session = db.get(BodyPhotoSession, UUID(str(session_id)))
    assert session is not None
    session.state = BodyPhotoSessionState.QUEUED
    db.add(
        BodyAnalysis(
            session_id=session.id,
            revision=1,
            provider="openrouter",
            model_id="vision-model",
            prompt_version="body-v1",
            schema_version="1.0",
            status=BodyAnalysisStatus.FAILED,
            error_code="photo_validation_failed",
        )
    )
    db.commit()

    response = _upload(client, session_id, "side", _png(color=(90, 80, 70)))

    assert response.status_code == 200
    assert response.json()["state"] == "uploaded"


def test_session_routes_require_authentication_and_trusted_origin(client: TestClient) -> None:
    anonymous = client.post(
        "/api/v1/body-photo-sessions",
        headers=ORIGIN,
        json={"purpose": "initial_plan"},
    )
    assert anonymous.status_code == 401
    assert client.get("/api/v1/body-photo-sessions").status_code == 401

    _register(client, "photo-origin@example.com")
    untrusted = client.post(
        "/api/v1/body-photo-sessions",
        json={"purpose": "initial_plan"},
    )
    assert untrusted.status_code == 403


def test_every_session_mutation_rejects_missing_trusted_origin(client: TestClient) -> None:
    _register(client, "photo-mutations@example.com")
    created = _create_session(client)
    session_id = created["id"]

    upload = client.put(
        f"/api/v1/body-photo-sessions/{session_id}/photos/front",
        files={"file": ("front.png", _png(), "image/png")},
    )
    submit = client.post(
        f"/api/v1/body-photo-sessions/{session_id}/submit",
        json=_consents(),
    )
    consent = client.post(
        f"/api/v1/body-photo-sessions/{session_id}/consents/model-training",
        json={"granted": False, "version": "training-v1"},
    )
    delete = client.delete(f"/api/v1/body-photo-sessions/{session_id}")

    assert [upload.status_code, submit.status_code, consent.status_code, delete.status_code] == [
        403,
        403,
        403,
        403,
    ]


def test_upload_cors_preflight_allows_multipart_content(client: TestClient) -> None:
    response = client.options(
        "/api/v1/body-photo-sessions/00000000-0000-0000-0000-000000000000/photos/front",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert "PUT" in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()


def test_upload_accepts_standardized_photo_without_obsolete_crop_evidence(
    client: TestClient,
) -> None:
    _register(client, "photo-client-crop-name@example.com")
    created = _create_session(client)
    accepted = _upload(client, created["id"], "front")

    assert accepted.status_code == 200
    photo = accepted.json()["photos"][0]
    assert "client_crop_confidence" not in photo
    assert "client_crop_confirmed" not in photo
    assert "server_geometry_checked" not in photo


def test_owner_can_create_list_and_read_safe_session_dtos(client: TestClient) -> None:
    _register(client, "photo-owner@example.com")
    created = _create_session(client, "progress_check")

    detail = client.get(f"/api/v1/body-photo-sessions/{created['id']}")
    listing = client.get("/api/v1/body-photo-sessions")

    assert detail.status_code == 200
    assert listing.status_code == 200
    assert listing.json()["items"][0]["id"] == created["id"]
    assert detail.json()["purpose"] == "progress_check"
    assert detail.json()["state"] == "draft"
    assert detail.json()["photos"] == []
    assert "storage_key" not in detail.text
    assert "storage_path" not in detail.text


def test_cross_user_session_and_content_are_not_disclosed(
    client: TestClient,
    test_settings: Settings,
) -> None:
    test_settings.body_photo_storage_root = Path(test_settings.media_root).parent / "body-private"
    _register(client, "photo-a@example.com")
    created = _create_session(client)
    assert _upload(client, created["id"], "front").status_code == 200
    _logout(client)

    _register(client, "photo-b@example.com")
    detail = client.get(f"/api/v1/body-photo-sessions/{created['id']}")
    content = client.get(f"/api/v1/body-photo-sessions/{created['id']}/photos/front/content")

    assert detail.status_code == 404
    assert content.status_code == 404


def test_submit_requires_operational_consent_but_not_training_consent(
    client: TestClient,
    test_settings: Settings,
) -> None:
    test_settings.body_photo_storage_root = Path(test_settings.media_root).parent / "body-private"
    _register(client, "photo-consent@example.com")
    created = _create_session(client)
    for view in ("front", "side", "back"):
        assert _upload(client, created["id"], view).status_code == 200

    missing_operational = client.post(
        f"/api/v1/body-photo-sessions/{created['id']}/submit",
        headers=ORIGIN,
        json={
            "operational_processing": {"granted": False, "version": "operational-v1"},
            "model_training": {"granted": False, "version": "training-v1"},
        },
    )
    assert missing_operational.status_code == 422

    submitted = client.post(
        f"/api/v1/body-photo-sessions/{created['id']}/submit",
        headers=ORIGIN,
        json={"operational_processing": {"granted": True, "version": "operational-v1"}},
    )
    assert submitted.status_code == 200
    assert submitted.json()["state"] == "queued"
    assert submitted.json()["operational_processing_consent"]["granted"] is True
    assert submitted.json()["model_training_consent"]["granted"] is False
    assert submitted.json()["operational_processing_consent"]["recorded_at"]
    assert submitted.json()["model_training_consent"]["recorded_at"]


def test_training_consent_revocation_is_a_separate_immutable_event(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    test_settings.body_photo_storage_root = Path(test_settings.media_root).parent / "body-private"
    _register(client, "photo-revoke@example.com")
    created = _create_session(client)
    for view in ("front", "side", "back"):
        assert _upload(client, created["id"], view).status_code == 200
    assert (
        client.post(
            f"/api/v1/body-photo-sessions/{created['id']}/submit",
            headers=ORIGIN,
            json=_consents(training_granted=True),
        ).status_code
        == 200
    )

    revoked = client.post(
        f"/api/v1/body-photo-sessions/{created['id']}/consents/model-training",
        headers=ORIGIN,
        json={"granted": False, "version": "training-v2"},
    )

    assert revoked.status_code == 200
    assert revoked.json()["granted"] is False
    assert revoked.json()["version"] == "training-v2"
    rows = db.execute(
        text(
            "SELECT granted, version FROM body_photo_consents "
            "WHERE session_id = :session_id AND consent_type = 'model_training' "
            "ORDER BY recorded_at"
        ),
        {"session_id": UUID(str(created["id"]))},
    ).all()
    assert rows == [(True, "training-v1"), (False, "training-v2")]


def test_submit_rejects_missing_view_and_replacement_keeps_one_photo_per_view(
    client: TestClient,
    db: Session,
    test_settings: Settings,
) -> None:
    test_settings.body_photo_storage_root = Path(test_settings.media_root).parent / "body-private"
    _register(client, "photo-replace@example.com")
    created = _create_session(client)
    assert _upload(client, created["id"], "front", _png(color=(1, 2, 3))).status_code == 200
    replacement = _upload(client, created["id"], "front", _png(color=(9, 8, 7)))
    assert replacement.status_code == 200

    missing = client.post(
        f"/api/v1/body-photo-sessions/{created['id']}/submit",
        headers=ORIGIN,
        json=_consents(),
    )
    assert missing.status_code == 422
    assert (
        db.scalar(
            text("SELECT count(*) FROM body_photos WHERE session_id = :session_id"),
            {"session_id": UUID(str(created["id"]))},
        )
        == 1
    )
    stored_files = [
        path for path in test_settings.body_photo_storage_root.rglob("*") if path.is_file()
    ]
    assert len(stored_files) == 1


def test_protected_content_returns_normalized_bytes_only_to_owner(
    client: TestClient,
    test_settings: Settings,
) -> None:
    test_settings.body_photo_storage_root = Path(test_settings.media_root).parent / "body-private"
    _register(client, "photo-content@example.com")
    created = _create_session(client)
    original = _png(color=(10, 20, 30))
    assert _upload(client, created["id"], "front", original).status_code == 200

    content = client.get(f"/api/v1/body-photo-sessions/{created['id']}/photos/front/content")

    assert content.status_code == 200
    assert content.headers["content-type"] == "image/png"
    assert content.headers["cache-control"] == "private, no-store"
    assert content.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert content.content != original


def test_delete_removes_private_files_and_marks_session_deleted(
    client: TestClient,
    test_settings: Settings,
) -> None:
    test_settings.body_photo_storage_root = Path(test_settings.media_root).parent / "body-private"
    _register(client, "photo-delete@example.com")
    created = _create_session(client)
    assert _upload(client, created["id"], "front").status_code == 200

    deleted = client.delete(
        f"/api/v1/body-photo-sessions/{created['id']}",
        headers=ORIGIN,
    )

    assert deleted.status_code == 204
    assert [
        path for path in test_settings.body_photo_storage_root.rglob("*") if path.is_file()
    ] == []
