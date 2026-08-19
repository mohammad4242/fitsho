from __future__ import annotations

from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.workout_cycles.models import WorkoutCycle
from tests.workout_cycles.test_weekly_check_in_api import ORIGIN, _plan_with_cycle, _register, _user


def _feedback_payload() -> dict[str, object]:
    return {
        "overall_difficulty": "appropriate",
        "overall_recovery": "good",
        "overall_satisfaction": "satisfied",
        "strength_progress": "improved",
        "muscle_progress": "unchanged",
        "endurance_progress": "improved",
        "energy_progress": "improved",
        "performance_changes": "I completed the final week consistently.",
        "pain_or_limitation_feedback": "",
        "note_optional": "Ready for the next cycle.",
    }


def test_completion_feedback_routes_are_registered(client: TestClient) -> None:
    paths = client.app.openapi()["paths"]

    path = "/api/v1/workout-cycles/current/completion-feedback"
    assert path in paths
    assert "get" in paths[path]
    assert "put" in paths[path]


def test_get_reports_due_feedback_for_an_ending_cycle(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"completion-get-{uuid4()}@example.com")
    _plan, cycle, _prescribed = _plan_with_cycle(db, user_id, days_ago=29)

    response = client.get("/api/v1/workout-cycles/current/completion-feedback")

    assert response.status_code == 200
    assert response.json() == {
        "cycle_id": str(cycle.id),
        "status": "active",
        "duration_weeks": 4,
        "current_week": 4,
        "is_due": True,
        "feedback_id": None,
        "feedback": None,
        "submitted_at": None,
    }


def test_put_completes_cycle_and_persists_structured_feedback(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"completion-put-{uuid4()}@example.com")
    _plan, cycle, _prescribed = _plan_with_cycle(db, user_id, days_ago=29)

    response = client.put(
        "/api/v1/workout-cycles/current/completion-feedback",
        headers=ORIGIN,
        json=_feedback_payload(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["cycle_id"] == str(cycle.id)
    assert body["status"] == "completed"
    assert body["is_due"] is False
    assert body["feedback_id"] is not None
    assert body["feedback"]["overall_difficulty"] == "appropriate"
    assert body["feedback"]["overall_satisfaction"] == "satisfied"
    assert body["feedback"]["performance_changes"] == _feedback_payload()["performance_changes"]

    db.refresh(cycle)
    assert cycle.status.value == "completed"
    assert cycle.completion_feedback is not None
    assert cycle.completion_feedback.id == UUID(body["feedback_id"])


def test_repeated_completion_submission_is_idempotent(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"completion-repeat-{uuid4()}@example.com")
    _plan, cycle, _prescribed = _plan_with_cycle(db, user_id, days_ago=29)
    path = "/api/v1/workout-cycles/current/completion-feedback"

    first = client.put(path, headers=ORIGIN, json=_feedback_payload())
    second = client.put(path, headers=ORIGIN, json=_feedback_payload())

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["feedback_id"] == first.json()["feedback_id"]
    assert db.get(WorkoutCycle, cycle.id).completion_feedback is not None


def test_completion_before_nominal_cycle_end_is_rejected(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"completion-early-{uuid4()}@example.com")
    _plan_with_cycle(db, user_id, days_ago=7)

    response = client.put(
        "/api/v1/workout-cycles/current/completion-feedback",
        headers=ORIGIN,
        json=_feedback_payload(),
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Workout cycle has not reached its end"}


def test_another_users_cycle_is_never_exposed(
    client: TestClient,
    db: Session,
) -> None:
    owner = _user(db, "completion-owner")
    _plan_with_cycle(db, owner.id, days_ago=29)
    _register(client, f"completion-other-{uuid4()}@example.com")

    response = client.get("/api/v1/workout-cycles/current/completion-feedback")

    assert response.status_code == 404
    assert response.json() == {"detail": "No workout cycle available"}
