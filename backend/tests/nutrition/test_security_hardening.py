import io
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.nutrition.models import NutritionLabDocument, NutritionSecurityAuditEvent
from app.nutrition.retention import cleanup_private_nutrition_files
from tests.nutrition.test_weekly_plan_api import ORIGIN


def _register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201


def _pdf() -> bytes:
    return b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF"


def _image() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (80, 80), "white").save(output, "PNG")
    return output.getvalue()


def test_lab_download_requires_short_lived_actor_bound_grant(
    client: TestClient,
) -> None:
    _register(client, "secure-lab@example.com")
    uploaded = client.post(
        "/api/v1/nutrition/labs",
        headers=ORIGIN,
        files={"file": ("blood.pdf", _pdf(), "application/pdf")},
    )
    assert uploaded.status_code == 201
    document_id = uploaded.json()["id"]

    assert client.get(f"/api/v1/nutrition/labs/{document_id}/file").status_code == 403
    grant = client.post(
        f"/api/v1/nutrition/labs/{document_id}/access-grant", headers=ORIGIN
    )
    assert grant.status_code == 200
    access_url = grant.json()["access_url"]
    assert grant.json()["expires_in_seconds"] <= 300
    assert client.get(access_url).content == _pdf()

    token = access_url.rsplit("token=", 1)[1]
    tampered = client.get(f"/api/v1/nutrition/labs/{document_id}/file?token={token}x")
    assert tampered.status_code == 403

    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204
    _register(client, "other-lab@example.com")
    assert client.get(access_url).status_code == 403
    assert (
        client.post(
            f"/api/v1/nutrition/labs/{document_id}/access-grant", headers=ORIGIN
        ).status_code
        == 404
    )


def test_duplicate_lab_upload_reuses_private_document_and_audits_metadata_only(
    client: TestClient, db: Session
) -> None:
    _register(client, "dedupe-lab@example.com")
    first = client.post(
        "/api/v1/nutrition/labs",
        headers=ORIGIN,
        files={"file": ("first.pdf", _pdf(), "application/pdf")},
        data={"user_note": "private medical note"},
    )
    second = client.post(
        "/api/v1/nutrition/labs",
        headers=ORIGIN,
        files={"file": ("copy.pdf", _pdf(), "application/pdf")},
        data={"user_note": "different private note"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["duplicate"] is True
    assert db.scalar(select(func.count()).select_from(NutritionLabDocument)) == 1
    events = db.scalars(select(NutritionSecurityAuditEvent)).all()
    assert {event.event_type for event in events} >= {"lab_uploaded", "lab_duplicate_reused"}
    assert "private medical note" not in str([event.metadata_snapshot for event in events])


def test_lab_upload_rejects_active_pdf_content(client: TestClient) -> None:
    _register(client, "unsafe-lab@example.com")
    response = client.post(
        "/api/v1/nutrition/labs",
        headers=ORIGIN,
        files={
            "file": (
                "unsafe.pdf",
                b"%PDF-1.4\n<</JavaScript (alert)>>\n%%EOF",
                "application/pdf",
            )
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_LAB_DOCUMENT"


def test_lab_upload_rate_limit_is_database_backed(
    client: TestClient, test_settings
) -> None:  # type: ignore[no-untyped-def]
    test_settings.nutrition_lab_upload_rate_limit = 1
    _register(client, "limited-lab@example.com")
    first = client.post(
        "/api/v1/nutrition/labs",
        headers=ORIGIN,
        files={"file": ("first.pdf", _pdf(), "application/pdf")},
    )
    second = client.post(
        "/api/v1/nutrition/labs",
        headers=ORIGIN,
        files={"file": ("second.png", _image(), "image/png")},
    )
    assert first.status_code == 201
    assert second.status_code == 429
    assert second.headers["Retry-After"]


def test_retention_removes_private_file_but_preserves_lab_audit_record(
    client: TestClient, db: Session, test_settings
) -> None:  # type: ignore[no-untyped-def]
    _register(client, "retention-lab@example.com")
    uploaded = client.post(
        "/api/v1/nutrition/labs",
        headers=ORIGIN,
        files={"file": ("blood.pdf", _pdf(), "application/pdf")},
    )
    row = db.get(NutritionLabDocument, uploaded.json()["id"])
    assert row is not None
    row.retained_until = datetime.now(UTC).date() - timedelta(days=1)
    db.commit()

    result = cleanup_private_nutrition_files(db, test_settings, now=datetime.now(UTC))

    db.refresh(row)
    assert result.lab_documents_purged == 1
    assert row.purged_at is not None
    assert db.get(NutritionLabDocument, row.id) is not None
