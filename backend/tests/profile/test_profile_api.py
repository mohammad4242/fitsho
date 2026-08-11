from datetime import date
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
    "training_location": "gym",
    "home_training_setup": None,
    "session_duration_minutes": 60,
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
    assert response.json()["training_location"] == "gym"
    assert response.json()["home_training_setup"] is None
    assert response.json()["session_duration_minutes"] == 60
    assert db.get(UserProfile, user_id) is not None
    measurements = db.scalars(
        select(BodyMeasurement).where(BodyMeasurement.user_id == user_id)
    ).all()
    assert len(measurements) == 1


def test_create_profile_persists_first_month_experience(
    client: TestClient, db: Session
) -> None:
    user_id = register(client, "first-month-profile@example.com")

    response = client.post(
        "/api/v1/profile",
        headers=ORIGIN,
        json={**VALID_PROFILE, "experience_level": "first_month"},
    )

    assert response.status_code == 201
    assert response.json()["experience_level"] == "first_month"
    profile = db.get(UserProfile, user_id)
    assert profile is not None
    assert profile.experience_level is not None
    assert profile.experience_level.value == "first_month"


@pytest.mark.parametrize(
    "home_training_setup",
    ["bodyweight_only", "dumbbells_available"],
)
def test_create_home_profile_stores_selected_setup(
    client: TestClient,
    db: Session,
    home_training_setup: str,
) -> None:
    user_id = register(client, f"{home_training_setup}@example.com")
    response = client.post(
        "/api/v1/profile",
        headers=ORIGIN,
        json={
            **VALID_PROFILE,
            "training_location": "home",
            "home_training_setup": home_training_setup,
        },
    )

    assert response.status_code == 201
    assert response.json()["home_training_setup"] == home_training_setup
    profile = db.get(UserProfile, user_id)
    assert profile is not None
    assert profile.home_training_setup is not None
    assert profile.home_training_setup.value == home_training_setup


def test_create_home_profile_rejects_missing_setup(client: TestClient) -> None:
    register(client, "missing-home-setup@example.com")

    response = client.post(
        "/api/v1/profile",
        headers=ORIGIN,
        json={
            **VALID_PROFILE,
            "training_location": "home",
            "home_training_setup": None,
        },
    )

    assert response.status_code == 422


def test_create_gym_profile_discards_home_setup(client: TestClient, db: Session) -> None:
    user_id = register(client, "gym-normalization@example.com")

    response = client.post(
        "/api/v1/profile",
        headers=ORIGIN,
        json={**VALID_PROFILE, "home_training_setup": "bodyweight_only"},
    )

    assert response.status_code == 201
    assert response.json()["home_training_setup"] is None
    profile = db.get(UserProfile, user_id)
    assert profile is not None
    assert profile.home_training_setup is None


def test_create_profile_rejects_unsupported_session_duration(client: TestClient) -> None:
    register(client, "invalid-duration@example.com")

    response = client.post(
        "/api/v1/profile",
        headers=ORIGIN,
        json={**VALID_PROFILE, "session_duration_minutes": 50},
    )

    assert response.status_code == 422


def test_training_profile_under_18_uses_stable_age_domain_error(client: TestClient) -> None:
    register(client, "minor-training@example.com")
    today = date.today()
    minor_birth_date = date(today.year - 17, today.month, min(today.day, 28)).isoformat()

    response = client.post(
        "/api/v1/profile",
        headers=ORIGIN,
        json={**VALID_PROFILE, "birth_date": minor_birth_date},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "AGE_NOT_SUPPORTED"


def test_get_profile_returns_404_until_onboarding_is_complete(client: TestClient) -> None:
    register(client)
    response = client.get("/api/v1/profile")

    assert response.status_code == 404
    assert response.json() == {"detail": "Fitness profile not found"}


def test_selecting_product_mode_creates_the_single_profile_draft(client: TestClient) -> None:
    user_id = register(client, "mode-selection@example.com")

    response = client.post(
        "/api/v1/profile/mode",
        headers=ORIGIN,
        json={"product_mode": "both"},
    )

    assert response.status_code == 201
    assert response.json() == {
        "user_id": str(user_id),
        "product_mode": "both",
        "completion_state": "shared_profile_incomplete",
    }

    profile = client.get("/api/v1/profile/status")
    assert profile.status_code == 200
    assert profile.json()["product_mode"] == "both"
    assert profile.json()["completion_state"] == "shared_profile_incomplete"


def test_profile_status_requires_explicit_mode_for_a_new_user(client: TestClient) -> None:
    user_id = register(client, "mode-required@example.com")

    response = client.get("/api/v1/profile/status")

    assert response.status_code == 200
    assert response.json() == {
        "user_id": str(user_id),
        "product_mode": None,
        "completion_state": "product_mode_not_selected",
    }


def test_changing_mode_preserves_the_completed_training_profile(client: TestClient) -> None:
    register(client, "mode-change@example.com")
    assert client.post("/api/v1/profile", headers=ORIGIN, json=VALID_PROFILE).status_code == 201

    changed = client.post(
        "/api/v1/profile/mode",
        headers=ORIGIN,
        json={"product_mode": "both"},
    )

    assert changed.status_code == 201
    assert changed.json()["completion_state"] == "nutrition_onboarding_incomplete"
    profile = client.get("/api/v1/profile")
    assert profile.status_code == 200
    assert profile.json()["display_name"] == "Mohammad"
    assert profile.json()["current_weight_kg"] == 76.5


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


def test_profile_stores_normalized_training_cautions_and_plan_duration(
    client: TestClient,
    db: Session,
) -> None:
    user_id = register(client, "cautions@example.com")

    response = client.post(
        "/api/v1/profile",
        headers=ORIGIN,
        json={
            **VALID_PROFILE,
            "training_cautions": ["lower_back", "wrist"],
            "plan_duration_weeks": 6,
        },
    )

    assert response.status_code == 201
    assert response.json()["training_cautions"] == ["lower_back", "wrist"]
    assert response.json()["plan_duration_weeks"] == 6
    profile = db.get(UserProfile, user_id)
    assert profile is not None
    assert [item.caution.value for item in profile.training_caution_items] == [
        "lower_back",
        "wrist",
    ]


def test_profile_rejects_duplicate_training_cautions(client: TestClient) -> None:
    register(client, "duplicate-cautions@example.com")

    response = client.post(
        "/api/v1/profile",
        headers=ORIGIN,
        json={**VALID_PROFILE, "training_cautions": ["knee", "knee"]},
    )

    assert response.status_code == 422
