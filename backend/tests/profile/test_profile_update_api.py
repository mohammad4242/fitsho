from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
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
    "training_location": "home",
    "home_training_setup": "dumbbells_available",
    "session_duration_minutes": 60,
    "physical_limitations": None,
}


def register(client: TestClient, email: str = "profile-update@example.com") -> UUID:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def create_profile(client: TestClient) -> None:
    response = client.post("/api/v1/profile", headers=ORIGIN, json=VALID_PROFILE)
    assert response.status_code == 201


def test_patch_updates_stable_fields_and_appends_changed_weight(
    client: TestClient, db: Session
) -> None:
    user_id = register(client)
    create_profile(client)

    response = client.patch(
        "/api/v1/profile",
        headers=ORIGIN,
        json={"display_name": "New Name", "current_weight_kg": 75.25},
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "New Name"
    assert response.json()["current_weight_kg"] == 75.25
    assert (
        db.scalar(
            select(func.count())
            .select_from(BodyMeasurement)
            .where(BodyMeasurement.user_id == user_id)
        )
        == 2
    )


def test_patch_same_weight_is_idempotent(client: TestClient, db: Session) -> None:
    user_id = register(client)
    create_profile(client)

    first = client.patch("/api/v1/profile", headers=ORIGIN, json={"current_weight_kg": 76.5})
    second = client.patch("/api/v1/profile", headers=ORIGIN, json={"current_weight_kg": 76.5})

    assert first.status_code == second.status_code == 200
    assert (
        db.scalar(
            select(func.count())
            .select_from(BodyMeasurement)
            .where(BodyMeasurement.user_id == user_id)
        )
        == 1
    )


def test_patch_updates_optional_circumferences_as_a_new_measurement(
    client: TestClient, db: Session
) -> None:
    user_id = register(client, "profile-circumferences@example.com")
    create_profile(client)

    response = client.patch(
        "/api/v1/profile",
        headers=ORIGIN,
        json={
            "shoulder_circumference_cm": 122.5,
            "waist_circumference_cm": 84,
            "hip_circumference_cm": 98.25,
        },
    )

    assert response.status_code == 200
    assert response.json()["shoulder_circumference_cm"] == 122.5
    assert response.json()["waist_circumference_cm"] == 84
    assert response.json()["hip_circumference_cm"] == 98.25
    assert response.json()["circumferences_measured_at"] is not None
    assert (
        db.scalar(
            select(func.count())
            .select_from(BodyMeasurement)
            .where(BodyMeasurement.user_id == user_id)
        )
        == 2
    )


def test_patch_rejects_empty_body(client: TestClient) -> None:
    register(client)
    create_profile(client)

    response = client.patch("/api/v1/profile", headers=ORIGIN, json={})

    assert response.status_code == 422


def test_patch_rejects_explicit_null_for_required_field(client: TestClient) -> None:
    register(client)
    create_profile(client)

    response = client.patch("/api/v1/profile", headers=ORIGIN, json={"display_name": None})

    assert response.status_code == 422


def test_patch_clears_limitations_with_null(client: TestClient) -> None:
    register(client)
    create_profile(client)

    response = client.patch(
        "/api/v1/profile",
        headers=ORIGIN,
        json={"physical_limitations": None},
    )

    assert response.status_code == 200
    assert response.json()["physical_limitations"] is None


def test_patch_switching_to_gym_clears_home_training_setup(
    client: TestClient,
    db: Session,
) -> None:
    user_id = register(client)
    create_profile(client)

    response = client.patch(
        "/api/v1/profile",
        headers=ORIGIN,
        json={"training_location": "gym"},
    )

    assert response.status_code == 200
    assert response.json()["training_location"] == "gym"
    assert response.json()["home_training_setup"] is None
    profile = db.get(UserProfile, user_id)
    assert profile is not None
    assert profile.home_training_setup is None


def test_patch_switching_to_home_requires_setup(client: TestClient) -> None:
    register(client)
    create_profile(client)
    assert (
        client.patch(
            "/api/v1/profile",
            headers=ORIGIN,
            json={"training_location": "gym"},
        ).status_code
        == 200
    )

    response = client.patch(
        "/api/v1/profile",
        headers=ORIGIN,
        json={"training_location": "home"},
    )

    assert response.status_code == 422


def test_patch_returns_404_for_missing_profile(client: TestClient) -> None:
    register(client)

    response = client.patch("/api/v1/profile", headers=ORIGIN, json={"display_name": "New Name"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Fitness profile not found"}


def test_patch_requires_authenticated_user(client: TestClient) -> None:
    response = client.patch("/api/v1/profile", headers=ORIGIN, json={"display_name": "New Name"})

    assert response.status_code == 401


@pytest.mark.parametrize("headers", [{}, {"Origin": "http://evil.example"}])
def test_patch_rejects_missing_or_untrusted_origin(
    client: TestClient, headers: dict[str, str]
) -> None:
    register(client)
    create_profile(client)

    response = client.patch("/api/v1/profile", headers=headers, json={"display_name": "New Name"})

    assert response.status_code == 403


def test_patch_cors_preflight_allows_patch(client: TestClient) -> None:
    response = client.options(
        "/api/v1/profile",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "PATCH",
        },
    )

    assert response.status_code == 200
    assert "PATCH" in response.headers["access-control-allow-methods"]


def test_patch_commit_failure_rolls_back_profile_and_new_measurement(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = register(client)
    create_profile(client)
    original_commit = db.commit

    def unavailable_commit() -> None:
        raise OperationalError("COMMIT", {}, Exception("database unavailable"))

    monkeypatch.setattr(db, "commit", unavailable_commit)
    response = client.patch(
        "/api/v1/profile",
        headers=ORIGIN,
        json={"display_name": "New Name", "current_weight_kg": 75.25},
    )
    monkeypatch.setattr(db, "commit", original_commit)

    assert response.status_code == 503
    assert response.json() == {"detail": "Service temporarily unavailable"}
    profile = db.get(UserProfile, user_id)
    assert profile is not None
    assert profile.display_name == "Mohammad"
    assert (
        db.scalar(
            select(func.count())
            .select_from(BodyMeasurement)
            .where(BodyMeasurement.user_id == user_id)
        )
        == 1
    )


def test_patch_replaces_training_cautions_only_when_supplied(
    client: TestClient,
    db: Session,
) -> None:
    user_id = register(client, "replace-cautions@example.com")
    response = client.post(
        "/api/v1/profile",
        headers=ORIGIN,
        json={**VALID_PROFILE, "training_cautions": ["lower_back", "wrist"]},
    )
    assert response.status_code == 201

    unchanged = client.patch(
        "/api/v1/profile",
        headers=ORIGIN,
        json={"display_name": "New Name"},
    )
    assert unchanged.status_code == 200
    assert unchanged.json()["training_cautions"] == ["lower_back", "wrist"]

    replaced = client.patch(
        "/api/v1/profile",
        headers=ORIGIN,
        json={"training_cautions": ["knee"]},
    )
    assert replaced.status_code == 200
    assert replaced.json()["training_cautions"] == ["knee"]
    profile = db.get(UserProfile, user_id)
    assert profile is not None
    assert [item.caution.value for item in profile.training_caution_items] == ["knee"]
