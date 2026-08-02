from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.exercises.service import seed_exercises
from app.training_templates.service import seed_training_program_templates

ORIGIN = {"Origin": "http://localhost:5173"}


def _register(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201


def _seed_library(db: Session) -> None:
    seed_exercises(db)
    seed_training_program_templates(db)


def _make_current_user_admin(client: TestClient, db: Session) -> None:
    _register(client, "admin-templates@example.com")
    user = db.scalar(select(User).where(User.email == "admin-templates@example.com"))
    assert user is not None
    user.is_admin = True
    db.commit()


def test_training_template_library_requires_admin_access(client: TestClient, db: Session) -> None:
    _seed_library(db)

    anonymous = client.get("/api/v1/admin/training-program-templates")
    assert anonymous.status_code == 401

    _register(client, "member-templates@example.com")
    member = client.get("/api/v1/admin/training-program-templates")
    assert member.status_code == 403


def test_admin_lists_complete_four_day_template_details(client: TestClient, db: Session) -> None:
    _seed_library(db)
    _make_current_user_admin(client, db)

    response = client.get("/api/v1/admin/training-program-templates?days_per_week=4")

    assert response.status_code == 200
    templates = response.json()["items"]
    assert len(templates) == 5
    classic = next(item for item in templates if item["slug"] == "four-day-classic-body-part")
    assert classic["training_level"] == "intermediate"
    assert "classic" in classic["focus_tags"]
    assert [day["title_fa"] for day in classic["days"]] == [
        "سینه + پشت بازو",
        "زیربغل + جلو بازو",
        "پا",
        "سرشانه + کول",
    ]
    first_slot = classic["days"][0]["slots"][0]
    assert first_slot["exercise"]["slug"] == "dumbbell-bench-press"
    placeholder = next(
        slot
        for day in classic["days"]
        for slot in day["slots"]
        if slot["exercise_slug_hint"] == "cable-pullover"
    )
    assert placeholder["exercise"] is None
    assert placeholder["placeholder_name_fa"] == "پلاور کابل"


def test_training_template_library_has_no_public_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/training-program-templates")

    assert response.status_code == 404
