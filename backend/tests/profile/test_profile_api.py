from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.profile.models import BodyMeasurement, UserProfile

ORIGIN = {"Origin": "http://localhost:5173"}
VALID_PROFILE = {
    "display_name": "  Mohammad  ",
    "birth_date": "2000-05-14",
    "sex": "male",
    "height_cm": 178,
    "current_weight_kg": 76.5,
    "fitness_goal": "build_muscle",
    "experience_level": "beginner",
    "training_days_per_week": 3,
    "physical_limitations": None,
}


def register(client: TestClient, email: str = "profile@example.com") -> UUID:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def login(client: TestClient, email: str) -> None:
    response = client.post(
        "/api/v1/auth/login",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 200


def test_create_profile_atomically_stores_profile_and_initial_weight(
    client: TestClient, db: Session
) -> None:
    user_id = register(client)
    response = client.post("/api/v1/profile", headers=ORIGIN, json=VALID_PROFILE)

    assert response.status_code == 201
    assert response.json()["display_name"] == "Mohammad"
    assert response.json()["current_weight_kg"] == 76.5
    assert db.get(UserProfile, user_id) is not None
    measurements = db.scalars(
        select(BodyMeasurement).where(BodyMeasurement.user_id == user_id)
    ).all()
    assert len(measurements) == 1


def test_get_profile_returns_404_until_onboarding_is_complete(client: TestClient) -> None:
    register(client)
    response = client.get("/api/v1/profile")

    assert response.status_code == 404
    assert response.json() == {"detail": "Fitness profile not found"}


def test_profile_endpoints_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/profile").status_code == 401
    assert client.post("/api/v1/profile", headers=ORIGIN, json=VALID_PROFILE).status_code == 401


def test_create_profile_rejects_duplicate_and_untrusted_origin(client: TestClient) -> None:
    register(client)
    assert client.post("/api/v1/profile", headers=ORIGIN, json=VALID_PROFILE).status_code == 201
    assert client.post("/api/v1/profile", headers=ORIGIN, json=VALID_PROFILE).status_code == 409
    assert client.post("/api/v1/profile", json=VALID_PROFILE).status_code == 403


def test_profiles_are_scoped_to_the_authenticated_user(client: TestClient) -> None:
    register(client, "a@example.com")
    profile_a = {**VALID_PROFILE, "display_name": "User A"}
    assert client.post("/api/v1/profile", headers=ORIGIN, json=profile_a).status_code == 201
    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204

    register(client, "b@example.com")
    profile_b = {**VALID_PROFILE, "display_name": "User B"}
    assert client.post("/api/v1/profile", headers=ORIGIN, json=profile_b).status_code == 201
    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204

    login(client, "a@example.com")
    assert client.get("/api/v1/profile").json()["display_name"] == "User A"
    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204

    login(client, "b@example.com")
    assert client.get("/api/v1/profile").json()["display_name"] == "User B"


def test_commit_failure_rolls_back_profile_and_measurement(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = register(client)
    original_commit = db.commit

    def unavailable_commit() -> None:
        raise OperationalError("COMMIT", {}, Exception("database unavailable"))

    monkeypatch.setattr(db, "commit", unavailable_commit)
    response = client.post("/api/v1/profile", headers=ORIGIN, json=VALID_PROFILE)
    monkeypatch.setattr(db, "commit", original_commit)

    assert response.status_code == 503
    assert response.json() == {"detail": "Service temporarily unavailable"}
    assert db.get(UserProfile, user_id) is None
    assert db.scalar(select(BodyMeasurement).where(BodyMeasurement.user_id == user_id)) is None


def test_profile_validation_does_not_echo_sensitive_text(client: TestClient) -> None:
    register(client)
    rejected_text = "sensitive medical detail"
    response = client.post(
        "/api/v1/profile",
        headers=ORIGIN,
        json={**VALID_PROFILE, "physical_limitations": rejected_text * 100},
    )

    assert response.status_code == 422
    assert rejected_text not in response.text
    assert all("input" not in error for error in response.json()["detail"])
