from __future__ import annotations

from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.workout_cycles.enums import WorkoutCycleStatus
from app.workout_cycles.models import WorkoutCycle
from app.workout_cycles.service import start_cycle
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutPlan

ORIGIN = {"Origin": "http://localhost:5173"}
PROFILE = {
    "display_name": "Cycle User",
    "birth_date": "2000-05-14",
    "sex": "male",
    "height_cm": 178,
    "current_weight_kg": 76.5,
    "fitness_goal": "build_muscle",
    "experience_level": "beginner",
    "training_days_per_week": 2,
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
    profile = client.post("/api/v1/profile", headers=ORIGIN, json=PROFILE)
    assert profile.status_code == 201
    return UUID(registration.json()["id"])


def _plan(db: Session, user_id: UUID, *, duration_weeks: int = 6) -> WorkoutPlan:
    plan = WorkoutPlan(
        user_id=user_id,
        status=WorkoutPlanStatus.ACTIVE,
        generation_signature="a" * 64,
        profile_snapshot={"plan_duration_weeks": duration_weeks},
        provider="fake",
        model_id="fake-model",
        prompt_version="v1",
        generation_policy_version="v1",
        candidate_set_hash="b" * 64,
        generation_method="coach_review",
    )
    db.add(plan)
    db.flush()
    return plan


def test_current_cycle_route_is_registered(client: TestClient) -> None:
    assert "get" in client.app.openapi()["paths"]["/api/v1/workout-cycles/current"]


def test_current_cycle_returns_the_authenticated_users_active_cycle(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register_and_complete_profile(client, f"current-cycle-{uuid4()}@example.com")
    plan = _plan(db, user_id, duration_weeks=6)
    cycle = start_cycle(db, user_id=user_id, workout_plan_id=plan.id)

    response = client.get("/api/v1/workout-cycles/current")

    assert response.status_code == 200
    assert response.json() == {
        "cycle_id": str(cycle.id),
        "workout_plan_id": str(plan.id),
        "started_at": cycle.started_at.isoformat().replace("+00:00", "Z"),
        "duration_weeks": 6,
        "status": WorkoutCycleStatus.ACTIVE.value,
        "current_week": 1,
    }


def test_current_cycle_returns_404_when_user_has_no_active_cycle(client: TestClient) -> None:
    _register_and_complete_profile(client, f"no-current-cycle-{uuid4()}@example.com")

    response = client.get("/api/v1/workout-cycles/current")

    assert response.status_code == 404
    assert response.json() == {"detail": "No active workout cycle"}


def test_current_cycle_never_returns_another_users_cycle(
    client: TestClient,
    db: Session,
) -> None:
    owner_id = _register_and_complete_profile(client, f"cycle-owner-{uuid4()}@example.com")
    plan = _plan(db, owner_id)
    owner_cycle = start_cycle(db, user_id=owner_id, workout_plan_id=plan.id)

    client.post("/api/v1/auth/logout", headers=ORIGIN)
    _register_and_complete_profile(client, f"cycle-other-{uuid4()}@example.com")

    response = client.get("/api/v1/workout-cycles/current")

    assert response.status_code == 404
    assert response.json() == {"detail": "No active workout cycle"}
    assert owner_cycle.user_id == owner_id
    assert db.query(WorkoutCycle).filter(WorkoutCycle.id == owner_cycle.id).one()
