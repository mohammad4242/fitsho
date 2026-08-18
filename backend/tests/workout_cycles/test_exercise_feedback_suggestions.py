from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.workout_cycles.enums import (
    WorkoutCycleStatus,
    WorkoutExerciseReplacementReason,
    WorkoutExerciseReplacementScope,
)
from app.workout_cycles.models import WorkoutExerciseReplacement
from app.workouts.enums import WorkoutPlanStatus
from tests.workout_cycles.test_replacement_api import (
    ORIGIN,
    _plan_with_cycle,
    _register,
    _user,
)


def test_repeated_persistent_replacements_create_grouped_suggestion(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"suggestion-repeat-{uuid4()}@example.com")
    _plan, prescribed, cycle, original, safe, _unsafe = _plan_with_cycle(db, user_id)
    assert cycle is not None

    payload = {
        "workout_plan_exercise_id": str(prescribed.id),
        "replacement_exercise_id": str(safe.id),
        "reason": "dislike",
        "scope": "persistent",
    }
    first = client.post(
        "/api/v1/workout-cycles/current/replacements", headers=ORIGIN, json=payload
    )
    second = client.post(
        "/api/v1/workout-cycles/current/replacements", headers=ORIGIN, json=payload
    )
    assert first.status_code == 201
    assert second.status_code == 201

    response = client.get(f"/api/v1/workout-cycles/{cycle.id}/exercise-feedback-suggestions")

    assert response.status_code == 200
    body = response.json()
    assert body["cycle_id"] == str(cycle.id)
    assert len(body["suggestions"]) == 1
    suggestion = body["suggestions"][0]
    assert suggestion["suggestion_kind"] == "negative_exercise_preference"
    assert suggestion["workout_plan_exercise_id"] == str(prescribed.id)
    assert suggestion["original_exercise_id"] == str(original.id)
    assert suggestion["replacement_count"] == 2
    assert suggestion["reasons"] == ["dislike"]
    assert suggestion["requires_confirmation"] is True
    assert suggestion["replacement_exercises"][0]["replacement_exercise_id"] == str(safe.id)
    assert suggestion["replacement_exercises"][0]["replacement_count"] == 2
    assert {UUID(value) for value in suggestion["replacement_exercises"][0]["replacement_ids"]} == {
        UUID(first.json()["id"]),
        UUID(second.json()["id"]),
    }


def test_temporary_replacements_do_not_create_permanent_suggestions(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"suggestion-temporary-{uuid4()}@example.com")
    _plan, prescribed, cycle, _original, safe, _unsafe = _plan_with_cycle(db, user_id)
    assert cycle is not None

    response = client.post(
        "/api/v1/workout-cycles/current/replacements",
        headers=ORIGIN,
        json={
            "workout_plan_exercise_id": str(prescribed.id),
            "replacement_exercise_id": str(safe.id),
            "reason": "temporary_unavailable",
            "scope": "this_time",
        },
    )
    assert response.status_code == 201

    suggestions = client.get(
        f"/api/v1/workout-cycles/{cycle.id}/exercise-feedback-suggestions"
    )

    assert suggestions.status_code == 200
    assert suggestions.json()["suggestions"] == []


def test_pain_replacements_are_separate_from_preference_suggestions(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"suggestion-pain-{uuid4()}@example.com")
    _plan, prescribed, cycle, _original, safe, _unsafe = _plan_with_cycle(db, user_id)
    assert cycle is not None

    for reason in ("dislike", "pain_or_discomfort"):
        response = client.post(
            "/api/v1/workout-cycles/current/replacements",
            headers=ORIGIN,
            json={
                "workout_plan_exercise_id": str(prescribed.id),
                "replacement_exercise_id": str(safe.id),
                "reason": reason,
                "scope": "persistent",
            },
        )
        assert response.status_code == 201

    response = client.get(f"/api/v1/workout-cycles/{cycle.id}/exercise-feedback-suggestions")

    assert response.status_code == 200
    suggestions = response.json()["suggestions"]
    assert {item["suggestion_kind"] for item in suggestions} == {
        "negative_exercise_preference",
        "safety",
    }
    safety = next(item for item in suggestions if item["suggestion_kind"] == "safety")
    assert safety["reasons"] == ["pain_or_discomfort"]
    assert safety["current_persistent_state"]["safety_signal_types"] == ["pain_or_discomfort"]


def test_existing_persistent_state_is_reflected_in_suggestion(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"suggestion-state-{uuid4()}@example.com")
    _plan, prescribed, cycle, _original, safe, _unsafe = _plan_with_cycle(db, user_id)
    assert cycle is not None

    response = client.post(
        "/api/v1/workout-cycles/current/replacements",
        headers=ORIGIN,
        json={
            "workout_plan_exercise_id": str(prescribed.id),
            "replacement_exercise_id": str(safe.id),
            "reason": "equipment_unavailable",
            "scope": "persistent",
        },
    )
    assert response.status_code == 201

    suggestions = client.get(
        f"/api/v1/workout-cycles/{cycle.id}/exercise-feedback-suggestions"
    )

    assert suggestions.status_code == 200
    suggestion = suggestions.json()["suggestions"][0]
    assert suggestion["suggestion_kind"] == "equipment_context"
    state = suggestion["current_persistent_state"]
    assert state["preference_types"] == ["equipment_unavailable"]
    assert state["safety_signal_types"] == []


def test_persistent_uncomfortable_maps_to_negative_preference_suggestion(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"suggestion-uncomfortable-{uuid4()}@example.com")
    _plan, prescribed, cycle, _original, safe, _unsafe = _plan_with_cycle(db, user_id)
    assert cycle is not None

    response = client.post(
        "/api/v1/workout-cycles/current/replacements",
        headers=ORIGIN,
        json={
            "workout_plan_exercise_id": str(prescribed.id),
            "replacement_exercise_id": str(safe.id),
            "reason": "uncomfortable",
            "scope": "persistent",
        },
    )
    assert response.status_code == 201

    suggestions = client.get(
        f"/api/v1/workout-cycles/{cycle.id}/exercise-feedback-suggestions"
    )

    assert suggestions.status_code == 200
    assert suggestions.json()["suggestions"][0]["suggestion_kind"] == (
        "negative_exercise_preference"
    )
    assert suggestions.json()["suggestions"][0]["reasons"] == ["uncomfortable"]


def test_no_replacement_history_returns_empty_suggestion_list(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"suggestion-empty-{uuid4()}@example.com")
    _plan, _prescribed, cycle, _original, _safe, _unsafe = _plan_with_cycle(db, user_id)
    assert cycle is not None

    response = client.get(f"/api/v1/workout-cycles/{cycle.id}/exercise-feedback-suggestions")

    assert response.status_code == 200
    assert response.json() == {"cycle_id": str(cycle.id), "suggestions": []}


def test_completed_cycle_suggestions_remain_available_and_owned(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"suggestion-completed-{uuid4()}@example.com")
    _plan, prescribed, cycle, _original, safe, _unsafe = _plan_with_cycle(db, user_id)
    assert cycle is not None
    cycle.status = WorkoutCycleStatus.COMPLETED
    cycle.completed_at = datetime.now(UTC)
    db.flush()

    db.add(
        _replacement_for_test(
            user_id=user_id,
            cycle_id=cycle.id,
            prescribed_id=prescribed.id,
            original_id=prescribed.exercise_id,
            replacement_id=safe.id,
        )
    )
    db.flush()

    response = client.get(f"/api/v1/workout-cycles/{cycle.id}/exercise-feedback-suggestions")

    assert response.status_code == 200
    assert response.json()["suggestions"][0]["replacement_count"] == 1


def test_another_users_replacement_history_is_not_exposed(
    client: TestClient,
    db: Session,
) -> None:
    _register(client, f"suggestion-owner-check-{uuid4()}@example.com")
    other = _user(db)
    _plan, prescribed, cycle, _original, safe, _unsafe = _plan_with_cycle(
        db, other.id, plan_status=WorkoutPlanStatus.SUPERSEDED
    )
    assert cycle is not None
    db.add(
        _replacement_for_test(
            user_id=other.id,
            cycle_id=cycle.id,
            prescribed_id=prescribed.id,
            original_id=prescribed.exercise_id,
            replacement_id=safe.id,
        )
    )
    db.flush()

    response = client.get(f"/api/v1/workout-cycles/{cycle.id}/exercise-feedback-suggestions")

    assert response.status_code == 404


def _replacement_for_test(
    *,
    user_id: UUID,
    cycle_id: UUID,
    prescribed_id: UUID,
    original_id: UUID,
    replacement_id: UUID,
)-> WorkoutExerciseReplacement:
    return WorkoutExerciseReplacement(
        user_id=user_id,
        cycle_id=cycle_id,
        workout_plan_exercise_id=prescribed_id,
        original_exercise_id=original_id,
        replacement_exercise_id=replacement_id,
        reason=WorkoutExerciseReplacementReason.DISLIKE,
        scope=WorkoutExerciseReplacementScope.PERSISTENT,
        week_number=1,
    )
