from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.body_analysis.enums import SpecialistRole
from app.body_analysis.models import UserSpecialistRole
from app.nutrition.models import (
    NutritionSupplementCatalogue,
    NutritionSupplementOrderAudit,
    NutritionWeeklyPlan,
)
from tests.nutrition.test_weekly_plan_api import (
    ORIGIN,
    _register_and_estimate,
    _seed_foods_and_prices,
)


def _setup(client: TestClient, db: Session) -> tuple[NutritionWeeklyPlan, User]:
    _register_and_estimate(client, "supplement-member@example.com")
    _seed_foods_and_prices(db)
    plan_id = client.post("/api/v1/nutrition/plans", headers=ORIGIN).json()["plan"]["id"]
    plan = db.scalar(select(NutritionWeeklyPlan).where(NutritionWeeklyPlan.id == plan_id))
    assert plan is not None and plan.review is not None
    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204
    assert (
        client.post(
            "/api/v1/auth/register",
            headers=ORIGIN,
            json={"email": "supplement-physician@example.com", "password": "long password"},
        ).status_code
        == 201
    )
    physician = db.scalar(select(User).where(User.email == "supplement-physician@example.com"))
    assert physician is not None
    db.add(UserSpecialistRole(user_id=physician.id, role=SpecialistRole.PHYSICIAN))
    plan.review.physician_user_id = physician.id
    db.flush()
    return plan, physician


def _catalogue(db: Session, *, calcium: int) -> NutritionSupplementCatalogue:
    row = NutritionSupplementCatalogue(
        slug=f"calcium-{calcium}",
        name_fa="مکمل کلسیم",
        name_en="Calcium",
        verification_status="verified",
        source_name="Test authoritative source",
        source_reference="https://example.test/calcium",
        active_ingredients=[{"name": "calcium"}],
        nutrient_contribution_per_unit={"calcium_mg": {"amount": calcium, "unit": "mg"}},
        contraindication_codes=[],
        allergen_codes=[],
        interaction_codes=[],
        upper_bound_rules=[],
    )
    db.add(row)
    db.flush()
    return row


def _payload(supplement_id: str) -> dict[str, object]:
    return {
        "supplement_id": supplement_id,
        "dose_amount": 1,
        "dose_unit": "tablet",
        "daily_units": 1,
        "frequency": "once_daily",
        "duration_days": 30,
        "instructions": "پس از غذا",
        "rationale": "بررسی و تصمیم پزشک",
        "rationale_user_visible": True,
        "linked_gap_codes": ["calcium"],
        "linked_lab_document_ids": [],
    }


def test_only_assigned_physician_can_prescribe_and_activate_with_audit(
    client: TestClient, db: Session
) -> None:
    plan, _physician = _setup(client, db)
    supplement = _catalogue(db, calcium=100)
    prescribed = client.post(
        f"/api/v1/nutrition/physician/plans/{plan.id}/supplement-orders",
        headers=ORIGIN,
        json=_payload(str(supplement.id)),
    )
    assert prescribed.status_code == 201, prescribed.text
    assert prescribed.json()["status"] == "prescribed"
    assert prescribed.json()["food_nutrient_contribution"] == {}
    assert float(prescribed.json()["supplement_nutrient_contribution"]["calcium_mg"]) == 100

    activated = client.post(
        f"/api/v1/nutrition/physician/supplement-orders/{prescribed.json()['id']}/transition",
        headers=ORIGIN,
        json={"status": "active"},
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "active"
    assert len(db.scalars(select(NutritionSupplementOrderAudit)).all()) == 2


def test_combined_exposure_over_upper_limit_is_hard_blocked(
    client: TestClient, db: Session
) -> None:
    plan, _physician = _setup(client, db)
    supplement = _catalogue(db, calcium=1_000_000)
    response = client.post(
        f"/api/v1/nutrition/physician/plans/{plan.id}/supplement-orders",
        headers=ORIGIN,
        json=_payload(str(supplement.id)),
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "SUPPLEMENT_UPPER_LIMIT_HARD_BLOCK"


def test_assigned_physician_lists_and_modifies_plan_supplement_orders(
    client: TestClient, db: Session
) -> None:
    plan, _physician = _setup(client, db)
    supplement = _catalogue(db, calcium=100)
    created = client.post(
        f"/api/v1/nutrition/physician/plans/{plan.id}/supplement-orders",
        headers=ORIGIN,
        json=_payload(str(supplement.id)),
    )
    assert created.status_code == 201
    order_id = created.json()["id"]

    listed = client.get(f"/api/v1/nutrition/physician/plans/{plan.id}/supplement-orders")
    assert listed.status_code == 200
    assert [row["id"] for row in listed.json()] == [order_id]

    payload = _payload(str(supplement.id))
    payload.update({"dose_amount": 2, "daily_units": 2, "duration_days": 14})
    modified = client.put(
        f"/api/v1/nutrition/physician/supplement-orders/{order_id}",
        headers=ORIGIN,
        json=payload,
    )
    assert modified.status_code == 200, modified.text
    assert modified.json()["dose_amount"] == 2
    assert modified.json()["duration_days"] == 14
    audits = db.scalars(
        select(NutritionSupplementOrderAudit).where(
            NutritionSupplementOrderAudit.order_id == order_id
        )
    ).all()
    assert [audit.action for audit in audits] == ["prescribed", "modified"]
