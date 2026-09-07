from datetime import date
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.body_analysis.enums import SpecialistRole
from app.body_analysis.models import UserSpecialistRole
from app.nutrition.models import (
    NutritionLabDocument,
    NutritionLabRequest,
    NutritionPlanPhysicianReview,
    NutritionReviewAuditEvent,
    NutritionWeeklyPlan,
)
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


def _login_physician(
    client: TestClient,
    db: Session,
    email: str = "physician@example.com",
) -> User:
    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204
    assert (
        client.post(
            "/api/v1/auth/register",
            headers=ORIGIN,
            json={"email": email, "password": "long password"},
        ).status_code
        == 201
    )
    physician = db.scalar(select(User).where(User.email == email))
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
    grant = client.post(f"/api/v1/nutrition/labs/{document_id}/access-grant", headers=ORIGIN)
    assert grant.status_code == 200
    assert client.get(grant.json()["access_url"]).status_code == 200

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
    physician_view = client.get(f"/api/v1/nutrition/physician/plans/{plan['id']}")
    assert physician_view.status_code == 200
    assert physician_view.json()["id"] == plan["id"]

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
    physician_grant = client.post(
        f"/api/v1/nutrition/labs/{document_id}/access-grant", headers=ORIGIN
    )
    assert physician_grant.status_code == 200
    assert client.get(physician_grant.json()["access_url"]).status_code == 200

    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204
    assert (
        client.post(
            "/api/v1/auth/login",
            headers=ORIGIN,
            json={"email": "clinical-member@example.com", "password": "long password"},
        ).status_code
        == 200
    )
    requests = client.get("/api/v1/nutrition/lab-requests")
    assert requests.status_code == 200
    assert requests.json()[0]["requested_tests"] == ["CBC"]
    assert requests.json()[0]["user_visible_reason"] == "برای بررسی ایمن‌تر برنامه"


def test_non_physician_cannot_access_review_queue(client: TestClient, db: Session) -> None:
    _member_plan(client, db)
    response = client.get("/api/v1/nutrition/physician/reviews")
    assert response.status_code == 403


def test_admin_status_does_not_grant_physician_role(client: TestClient, db: Session) -> None:
    _member_plan(client, db)
    member = db.scalar(select(User).where(User.email == "clinical-member@example.com"))
    assert member is not None
    member.is_admin = True
    db.flush()

    response = client.get("/api/v1/nutrition/physician/reviews")

    assert response.status_code == 403


def test_physician_cannot_access_ai_price_administration_endpoints(
    client: TestClient,
    db: Session,
) -> None:
    _member_plan(client, db)
    _login_physician(client, db, "price-boundary-physician@example.com")

    monitoring = client.get("/api/v1/nutrition/admin/monitoring")
    price_research = client.post(
        "/api/v1/nutrition/admin/foods/unknown/price-research",
        headers=ORIGIN,
    )

    assert monitoring.status_code == 403
    assert price_research.status_code == 403


def test_mixed_physician_admin_keeps_both_explicit_capabilities(
    client: TestClient,
    db: Session,
) -> None:
    _member_plan(client, db)
    physician = _login_physician(client, db, "mixed-physician-admin@example.com")
    physician.is_admin = True
    db.flush()

    physician_queue = client.get("/api/v1/nutrition/physician/reviews")
    admin_monitoring = client.get("/api/v1/nutrition/admin/monitoring")

    assert physician_queue.status_code == 200
    assert admin_monitoring.status_code == 200


def test_physician_rejection_requires_current_revision_and_cannot_be_replayed(
    client: TestClient,
    db: Session,
) -> None:
    plan = _member_plan(client, db)
    physician = _login_physician(client, db, "rejection-physician@example.com")
    review = next(
        item
        for item in client.get("/api/v1/nutrition/physician/reviews").json()
        if item["plan_id"] == plan["id"]
    )
    assert (
        client.post(
            f"/api/v1/nutrition/physician/reviews/{review['review_id']}/claim",
            headers=ORIGIN,
        ).status_code
        == 200
    )

    stale = client.post(
        f"/api/v1/nutrition/physician/plans/{plan['id']}/action",
        headers=ORIGIN,
        json={
            "expected_plan_revision_id": str(uuid4()),
            "action": "reject",
            "notes": "نسخهٔ قدیمی است",
        },
    )
    missing_notes = client.post(
        f"/api/v1/nutrition/physician/plans/{plan['id']}/action",
        headers=ORIGIN,
        json={
            "expected_plan_revision_id": plan["id"],
            "action": "reject",
            "notes": "  ",
        },
    )
    rejected = client.post(
        f"/api/v1/nutrition/physician/plans/{plan['id']}/action",
        headers=ORIGIN,
        json={
            "expected_plan_revision_id": plan["id"],
            "action": "reject",
            "notes": "به اطلاعات تکمیلی نیاز است",
        },
    )
    replay = client.post(
        f"/api/v1/nutrition/physician/plans/{plan['id']}/action",
        headers=ORIGIN,
        json={
            "expected_plan_revision_id": plan["id"],
            "action": "reject",
            "notes": "تلاش تکراری",
        },
    )

    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "STALE_PLAN_REVISION"
    assert missing_notes.status_code == 409
    assert missing_notes.json()["detail"]["code"] == "REVIEW_NOTES_REQUIRED"
    assert rejected.status_code == 200
    assert rejected.json()["review_status"] == "rejected"
    assert replay.status_code == 409
    assert replay.json()["detail"]["code"] == "REVIEW_NOT_IN_PROGRESS"

    audit_rows = db.scalars(
        select(NutritionReviewAuditEvent).where(
            NutritionReviewAuditEvent.review_id == review["review_id"]
        )
    ).all()
    rejection_events = [row for row in audit_rows if row.action == "reject"]
    assert len(rejection_events) == 1
    assert rejection_events[0].actor_user_id == physician.id
    assert rejection_events[0].metadata_snapshot == {
        "plan_id": plan["id"],
        "revision": plan["revision"],
    }


def test_assigned_review_cannot_be_taken_over_or_approved_by_another_physician(
    client: TestClient,
    db: Session,
) -> None:
    plan = _member_plan(client, db)
    first = _login_physician(client, db, "first-physician@example.com")
    review = next(
        item
        for item in client.get("/api/v1/nutrition/physician/reviews").json()
        if item["plan_id"] == plan["id"]
    )
    assert (
        client.post(
            f"/api/v1/nutrition/physician/reviews/{review['review_id']}/claim",
            headers=ORIGIN,
        ).status_code
        == 200
    )

    second = _login_physician(client, db, "second-physician@example.com")
    response = client.post(
        f"/api/v1/nutrition/physician/plans/{plan['id']}/action",
        headers=ORIGIN,
        json={
            "expected_plan_revision_id": plan["id"],
            "action": "approve",
            "notes": "تأیید",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "REVIEW_ASSIGNED_TO_ANOTHER_PHYSICIAN"
    persisted = db.scalar(
        select(NutritionPlanPhysicianReview).where(
            NutritionPlanPhysicianReview.plan_id == plan["id"]
        )
    )
    assert persisted is not None and persisted.physician_user_id == first.id
    assert persisted.physician_user_id != second.id


def test_assigned_physician_can_read_current_medical_context_only_for_the_assigned_case(
    client: TestClient,
    db: Session,
) -> None:
    plan = _member_plan(client, db)
    safety = client.put(
        "/api/v1/nutrition/safety",
        headers=ORIGIN,
        json={
            "conditions": [{"code": "kidney_disease", "details": "مرحله دوم"}],
            "medications": [{"name": "داروی نمونه", "dosage": "10 mg", "notes": "صبح"}],
            "dangerous_food_reaction_history": False,
            "pregnant": False,
            "breastfeeding": False,
            "eating_disorder_diagnosed": False,
            "eating_disorder_active_symptoms": False,
            "emergency_or_danger_symptoms": False,
            "complex_medication_food_interaction": False,
            "physician_dietary_restrictions": "نمک کم",
            "other_relevant_condition": "فشار خون",
        },
    )
    assert safety.status_code == 200, safety.text

    _login_physician(client, db, "context-physician@example.com")
    review = next(
        item
        for item in client.get("/api/v1/nutrition/physician/reviews").json()
        if item["plan_id"] == plan["id"]
    )
    assert (
        client.post(
            f"/api/v1/nutrition/physician/reviews/{review['review_id']}/claim",
            headers=ORIGIN,
        ).status_code
        == 200
    )

    context = client.get(f"/api/v1/nutrition/physician/plans/{plan['id']}/medical-context")

    assert context.status_code == 200, context.text
    assert context.json()["conditions"] == [{"code": "kidney_disease", "details": "مرحله دوم"}]
    assert context.json()["medications"] == [
        {"name": "داروی نمونه", "dosage": "10 mg", "notes": "صبح"}
    ]
    assert context.json()["physician_dietary_restrictions"] == "نمک کم"
    assert context.json()["other_relevant_condition"] == "فشار خون"
    assert context.json()["safety_reason_codes"]

    _login_physician(client, db, "unassigned-context-physician@example.com")
    denied = client.get(f"/api/v1/nutrition/physician/plans/{plan['id']}/medical-context")
    assert denied.status_code == 409
    assert denied.json()["detail"]["code"] == "REVIEW_ASSIGNED_TO_ANOTHER_PHYSICIAN"


def test_approval_requires_claim_and_activates_exact_due_revision(
    client: TestClient,
    db: Session,
) -> None:
    plan = _member_plan(client, db)
    _login_physician(client, db, "approval-physician@example.com")
    payload = {
        "expected_plan_revision_id": plan["id"],
        "action": "approve",
        "notes": "از نظر پزشکی تأیید شد",
        "internal_notes": "یادداشت محرمانه پزشک",
    }
    unclaimed = client.post(
        f"/api/v1/nutrition/physician/plans/{plan['id']}/action",
        headers=ORIGIN,
        json=payload,
    )
    assert unclaimed.status_code == 409
    assert unclaimed.json()["detail"]["code"] == "REVIEW_NOT_CLAIMED"

    review = next(
        item
        for item in client.get("/api/v1/nutrition/physician/reviews").json()
        if item["plan_id"] == plan["id"]
    )
    assert (
        client.post(
            f"/api/v1/nutrition/physician/reviews/{review['review_id']}/claim",
            headers=ORIGIN,
        ).status_code
        == 200
    )
    persisted = db.get(NutritionWeeklyPlan, plan["id"])
    assert persisted is not None
    persisted.start_date = date.today()
    db.commit()

    approved = client.post(
        f"/api/v1/nutrition/physician/plans/{plan['id']}/action",
        headers=ORIGIN,
        json=payload,
    )

    assert approved.status_code == 200, approved.text
    assert approved.json()["lifecycle_status"] == "active"
    assert approved.json()["physician_approved"] is True
    assert "internal_notes" not in approved.json()
    persisted = db.get(NutritionWeeklyPlan, plan["id"])
    assert persisted is not None and persisted.review is not None
    assert persisted.review.internal_notes == "یادداشت محرمانه پزشک"


def test_physician_queue_views_move_a_case_from_pending_to_claimed_to_approved(
    client: TestClient,
    db: Session,
) -> None:
    plan = _member_plan(client, db)
    physician = _login_physician(client, db, "queue-physician@example.com")

    pending = client.get("/api/v1/nutrition/physician/reviews?view=pending")

    assert pending.status_code == 200
    pending_case = next(item for item in pending.json() if item["plan_id"] == plan["id"])
    assert pending_case["member_display_name"] == "کاربر برنامه"
    assert pending_case["status"] == "pending"
    assert "internal_notes" not in pending_case
    assert client.get("/api/v1/nutrition/physician/reviews?view=claimed").json() == []

    claimed = client.post(
        f"/api/v1/nutrition/physician/reviews/{pending_case['review_id']}/claim",
        headers=ORIGIN,
    )

    assert claimed.status_code == 200
    claimed_cases = client.get("/api/v1/nutrition/physician/reviews?view=claimed").json()
    claimed_case = next(item for item in claimed_cases if item["plan_id"] == plan["id"])
    assert claimed_case["physician_user_id"] == str(physician.id)
    assert not any(
        item["plan_id"] == plan["id"]
        for item in client.get("/api/v1/nutrition/physician/reviews?view=pending").json()
    )

    persisted = db.get(NutritionWeeklyPlan, plan["id"])
    assert persisted is not None
    persisted.start_date = date.today()
    db.commit()
    approved = client.post(
        f"/api/v1/nutrition/physician/plans/{plan['id']}/action",
        headers=ORIGIN,
        json={
            "expected_plan_revision_id": plan["id"],
            "action": "approve",
            "notes": "نسخه نهایی تأیید شد",
            "internal_notes": "یادداشت خصوصی",
        },
    )

    assert approved.status_code == 200
    approved_cases = client.get("/api/v1/nutrition/physician/reviews?view=approved").json()
    approved_case = next(item for item in approved_cases if item["plan_id"] == plan["id"])
    assert approved_case["status"] == "approved"
    assert approved_case["reviewed_at"] is not None
    assert "internal_notes" not in approved_case

    _login_physician(client, db, "other-queue-physician@example.com")
    assert not any(
        item["plan_id"] == plan["id"]
        for item in client.get("/api/v1/nutrition/physician/reviews?view=approved").json()
    )


def test_assigned_physician_can_list_and_review_member_labs(
    client: TestClient,
    db: Session,
) -> None:
    plan = _member_plan(client, db)
    uploaded = client.post(
        "/api/v1/nutrition/labs",
        headers=ORIGIN,
        files={"file": ("blood.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
        data={"category": "blood_panel", "laboratory_name": "آزمایشگاه"},
    )
    assert uploaded.status_code == 201
    document_id = uploaded.json()["id"]
    _login_physician(client, db, "lab-review-physician@example.com")
    review = next(
        item
        for item in client.get("/api/v1/nutrition/physician/reviews").json()
        if item["plan_id"] == plan["id"]
    )
    assert (
        client.post(
            f"/api/v1/nutrition/physician/reviews/{review['review_id']}/claim",
            headers=ORIGIN,
        ).status_code
        == 200
    )

    listed = client.get(f"/api/v1/nutrition/physician/plans/{plan['id']}/labs")
    reviewed = client.put(
        f"/api/v1/nutrition/physician/labs/{document_id}/review",
        headers=ORIGIN,
        json={"review_status": "reviewed", "notes": "بررسی شد"},
    )

    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [document_id]
    assert reviewed.status_code == 200, reviewed.text
    row = db.get(NutritionLabDocument, document_id)
    assert row is not None and row.review_status == "reviewed"
    assert row.reviewed_at is not None
