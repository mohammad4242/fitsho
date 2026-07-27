from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.profile.models import BodyMeasurement, UserProfile

ORIGIN = {"Origin": "http://localhost:5173"}
VALID_PROFILE = {
    "display_name": "Mohammad",
    "birth_date": "2000-05-14",
    "sex": "male",
    "height_cm": 178,
    "current_weight_kg": 76.5,
    "fitness_goal": "build_muscle",
    "experience_level": "beginner",
    "training_days_per_week": 3,
    "training_location": "gym",
    "home_training_setup": None,
    "session_duration_minutes": 60,
    "physical_limitations": None,
}


def test_refresh_failure_rolls_back_profile_and_measurement(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registration = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": "refresh-failure@example.com", "password": "long password"},
    )
    assert registration.status_code == 201
    user_id = UUID(registration.json()["id"])
    original_refresh = db.refresh

    def unavailable_refresh(_instance: object) -> None:
        raise OperationalError("REFRESH", {}, Exception("database unavailable"))

    monkeypatch.setattr(db, "refresh", unavailable_refresh)
    response = client.post("/api/v1/profile", headers=ORIGIN, json=VALID_PROFILE)
    monkeypatch.setattr(db, "refresh", original_refresh)

    assert response.status_code == 503
    assert response.json() == {"detail": "Service temporarily unavailable"}
    assert db.get(UserProfile, user_id) is None
    assert db.scalar(select(BodyMeasurement).where(BodyMeasurement.user_id == user_id)) is None
