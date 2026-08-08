from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.body_analysis.enums import SpecialistRole
from app.body_analysis.models import UserSpecialistRole
from app.nutrition.models import NutritionLabRequest, NutritionWeeklyPlan
from tests.nutrition.test_weekly_plan_api import (
    ORIGIN,
    _register_and_estimate,
    _seed_foods_and_prices,
)


def _member_plan(client: TestClient, db: Session) -> dict[str, object]:
    _register_and_estimate(client, "clinical-member@example.com")
    _seed_foods_and_prices(db)
    response = client.post("/api/v1/nutrition/plans", headers=ORIGIN)
    assert response.status_code == 201
    return response.json()["plan"]


def _login_physician(client: TestClient, db: Session) -> User:
    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204
    assert (
        client.post(
            "/api/v1/auth/register",
            headers=ORIGIN,
            json={"email": "physician@example.com", "password": "long password"},
        ).status_code
        == 201
    )
    physician = db.scalar(select(User).where(User.email == "physician@example.com"))
    assert physician is not None
    db.add(UserSpecialistRole(user_id=physician.id, role=SpecialistRole.PHYSICIAN))
    db.flush()
    return physician


def test_lab_upload_is_private_and_physician_request_has_explicit_state(
    client: TestClient, db: Session
) -> None:
    plan = _member_plan(client, db)
    uploaded = client.post(
        "/api/v1/nutrition/labs",
        headers=ORIGIN,
        files={"file": ("blood.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
        data={"category": "blood_panel", "laboratory_name": "Test Lab"},
    )
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["id"]
    assert client.get(f"/api/v1/nutrition/labs/{document_id}/file").status_code == 200

    physician = _login_physician(client, db)
    queue = client.get("/api/v1/nutrition/physician/reviews")
    assert queue.status_code == 200
    review = next(item for item in queue.json() if item["plan_id"] == plan["id"])
    assert (
        client.post(
            f"/api/v1/nutrition/physician/reviews/{review['review_id']}/claim", headers=ORIGIN
        ).status_code
        == 200
    )

    request = client.post(
        f"/api/v1/nutrition/physician/plans/{plan['id']}/request-labs",
        headers=ORIGIN,
        json={
            "expected_plan_revision_id": plan["id"],
            "requested_tests": ["CBC"],
            "user_visible_reason": "برای بررسی ایمن‌تر برنامه",
        },
    )
    assert request.status_code == 200, request.text
    assert request.json()["status"] == "requested"
    persisted = db.scalar(select(NutritionWeeklyPlan).where(NutritionWeeklyPlan.id == plan["id"]))
    assert persisted is not None and persisted.lifecycle_status.value == "awaiting_lab_information"
    lab_request = db.scalar(select(NutritionLabRequest))
    assert lab_request is not None and lab_request.physician_user_id == physician.id
    assert client.get(f"/api/v1/nutrition/labs/{document_id}/file").status_code == 200


def test_non_physician_cannot_access_review_queue(client: TestClient, db: Session) -> None:
    _member_plan(client, db)
    response = client.get("/api/v1/nutrition/physician/reviews")
    assert response.status_code == 403
