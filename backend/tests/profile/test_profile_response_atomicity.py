from collections.abc import Callable
from typing import Any, Never

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

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


def test_create_response_does_not_query_after_commit(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registration = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": "post-commit-read@example.com", "password": "long password"},
    )
    assert registration.status_code == 201
    original_commit = db.commit
    original_execute: Callable[..., Any] = db.execute

    def unavailable_execute(*_args: object, **_kwargs: object) -> Never:
        raise OperationalError("SELECT", {}, Exception("database unavailable"))

    def commit_then_disable_reads() -> None:
        original_commit()
        monkeypatch.setattr(db, "execute", unavailable_execute)

    monkeypatch.setattr(db, "commit", commit_then_disable_reads)
    response = client.post("/api/v1/profile", headers=ORIGIN, json=VALID_PROFILE)
    monkeypatch.setattr(db, "execute", original_execute)
    monkeypatch.setattr(db, "commit", original_commit)

    assert response.status_code == 201
    assert response.json()["display_name"] == "Mohammad"
    assert response.json()["current_weight_kg"] == 76.5
