from typing import cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.schemas import ProviderErrorCode
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutPlan
from app.workouts.service import (
    GenerationCooldownError,
    WorkoutGenerationFailedError,
    WorkoutPlanGenerationResult,
)

ORIGIN = {"Origin": "http://localhost:5173"}
PROFILE = {
    "display_name": "Workout User",
    "birth_date": "2000-05-14",
    "sex": "male",
    "height_cm": 178,
    "current_weight_kg": 76.5,
    "fitness_goal": "build_muscle",
    "experience_level": "beginner",
    "training_days_per_week": 1,
    "training_location": "gym",
    "home_training_setup": None,
    "session_duration_minutes": 45,
    "physical_limitations": None,
}


def _register_and_complete_profile(client: TestClient, email: str) -> UUID:
    registration = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert registration.status_code == 201
    response = client.post("/api/v1/profile", headers=ORIGIN, json=PROFILE)
    assert response.status_code == 201
    return UUID(registration.json()["id"])


def _plan(db: Session, user_id: UUID) -> WorkoutPlan:
    plan = WorkoutPlan(
        user_id=user_id,
        status=WorkoutPlanStatus.ACTIVE,
        generation_signature="a" * 64,
        profile_snapshot={"fitness_goal": "build_muscle", "plan_duration_weeks": 4},
        provider="fake",
        model_id="fake-model",
        prompt_version="v1",
        generation_policy_version="v1",
        candidate_set_hash="b" * 64,
        generation_method="ai",
    )
    db.add(plan)
    db.commit()
    return plan


def test_workout_plan_routes_require_authentication(client: TestClient) -> None:
    assert client.get("/api/v1/workout-plans/active").status_code == 401
    assert client.post("/api/v1/workout-plans/generate", headers=ORIGIN).status_code == 401


def test_active_workout_plan_returns_not_found_without_a_plan(client: TestClient) -> None:
    _register_and_complete_profile(client, "no-plan@example.com")

    response = client.get("/api/v1/workout-plans/active")

    assert response.status_code == 404
    assert response.json() == {"detail": "No active workout plan"}


def test_active_workout_plan_reports_backend_staleness(client: TestClient, db: Session) -> None:
    user_id = _register_and_complete_profile(client, "stale-plan@example.com")
    _plan(db, user_id)

    response = client.get("/api/v1/workout-plans/active")

    assert response.status_code == 200
    assert response.json()["plan_duration_weeks"] == 4
    assert response.json()["is_stale"] is True


def test_workout_plan_is_scoped_to_its_owner(client: TestClient, db: Session) -> None:
    owner_id = _register_and_complete_profile(client, "owner-plan@example.com")
    plan = _plan(db, owner_id)
    response = client.get(f"/api/v1/workout-plans/{plan.id}")

    assert response.status_code == 200
    assert response.json()["id"] == str(plan.id)
    assert response.json()["plan_duration_weeks"] == 4
    assert response.json()["is_stale"] is False
    assert "provider" not in response.json()
    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204
    _register_and_complete_profile(client, "other-plan@example.com")

    assert client.get(f"/api/v1/workout-plans/{plan.id}").status_code == 404


def test_generate_uses_authenticated_user_and_returns_reuse_flag(
    client: TestClient, db: Session
) -> None:
    user_id = _register_and_complete_profile(client, "generate-plan@example.com")
    plan = _plan(db, user_id)
    called_user_ids: list[UUID] = []

    class FakeService:
        async def generate(self, current_user_id: UUID) -> WorkoutPlanGenerationResult:
            called_user_ids.append(current_user_id)
            return WorkoutPlanGenerationResult(plan=plan, reused=True)

    from app.workouts.dependencies import get_workout_generation_service

    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_workout_generation_service] = lambda: FakeService()
    response = client.post("/api/v1/workout-plans/generate", headers=ORIGIN)
    app.dependency_overrides.pop(get_workout_generation_service)

    assert response.status_code == 200
    assert response.json()["reused"] is True
    assert called_user_ids == [user_id]


def test_generate_returns_retry_after_during_a_generation_cooldown(
    client: TestClient,
) -> None:
    _register_and_complete_profile(client, "cooldown-plan@example.com")

    class FakeService:
        async def generate(self, current_user_id: UUID) -> WorkoutPlanGenerationResult:
            raise GenerationCooldownError(42)

    from app.workouts.dependencies import get_workout_generation_service

    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_workout_generation_service] = lambda: FakeService()
    response = client.post("/api/v1/workout-plans/generate", headers=ORIGIN)
    app.dependency_overrides.pop(get_workout_generation_service)

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "42"


@pytest.mark.parametrize(
    ("error_code", "expected_status"),
    [
        (ProviderErrorCode.TIMEOUT, 504),
        (ProviderErrorCode.MALFORMED_RESPONSE, 502),
        (ProviderErrorCode.RATE_LIMITED, 503),
    ],
)
def test_generate_maps_provider_failures_to_safe_statuses(
    client: TestClient,
    error_code: ProviderErrorCode,
    expected_status: int,
) -> None:
    _register_and_complete_profile(client, f"provider-{error_code.value}@example.com")

    class FakeService:
        async def generate(self, current_user_id: UUID) -> WorkoutPlanGenerationResult:
            raise WorkoutGenerationFailedError(error_code)

    from app.workouts.dependencies import get_workout_generation_service

    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_workout_generation_service] = lambda: FakeService()
    response = client.post("/api/v1/workout-plans/generate", headers=ORIGIN)
    app.dependency_overrides.pop(get_workout_generation_service)

    assert response.status_code == expected_status
    assert "error_code" not in response.json()
