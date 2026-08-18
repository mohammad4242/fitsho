from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.models import User
from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    ExerciseType,
    MediaType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
)
from app.exercises.models import Exercise
from app.workout_cycles.models import WorkoutCycle, WorkoutCycleWeeklyCheckIn
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanExercise

ORIGIN = {"Origin": "http://localhost:5173"}


def _register(client: TestClient, email: str) -> UUID:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def _user(db: Session, email_prefix: str) -> User:
    user = User(email=f"{email_prefix}-{uuid4()}@example.com", password_hash="hash")
    db.add(user)
    db.flush()
    return user


def _exercise(db: Session, slug: str) -> Exercise:
    exercise = Exercise(
        slug=f"{slug}-{uuid4().hex}",
        name_en=slug.replace("-", " ").title(),
        name_fa=f"حرکت {slug}",
        body_region=BodyRegion.UPPER_BODY,
        primary_muscle=MuscleGroup.CHEST,
        muscle_focus=MuscleFocus.MID_CHEST,
        difficulty=Difficulty.BEGINNER,
        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        exercise_type=ExerciseType.COMPOUND,
        instructions_en=["Set up.", "Move safely.", "Finish."],
        instructions_fa=["آماده شو.", "ایمن حرکت کن.", "تمام کن."],
        safety_notes_en=["Move with control."],
        safety_notes_fa=["کنترل‌شده حرکت کن."],
        media_path="/exercises/exercise-placeholder.svg",
        media_type=MediaType.PLACEHOLDER,
        is_active=True,
        is_programmable=True,
        needs_review=False,
    )
    db.add(exercise)
    db.flush()
    return exercise


def _plan_with_cycle(
    db: Session,
    user_id: UUID,
    *,
    days_ago: int = 0,
    training_days: int = 1,
) -> tuple[WorkoutPlan, WorkoutCycle, WorkoutPlanExercise]:
    plan = WorkoutPlan(
        user_id=user_id,
        status=WorkoutPlanStatus.ACTIVE,
        generation_signature="a" * 64,
        profile_snapshot={"plan_duration_weeks": 4},
        provider="fake",
        model_id="fake-model",
        prompt_version="v1",
        generation_policy_version="v1",
        candidate_set_hash="b" * 64,
        generation_method="coach_review",
    )
    for day_number in range(1, training_days + 1):
        day = WorkoutDay(
            day_number=day_number,
            title_en=f"Day {day_number}",
            title_fa=f"روز {day_number}",
            estimated_duration_minutes=20,
        )
        exercise = _exercise(db, f"weekly-api-{day_number}")
        day.exercises.append(
            WorkoutPlanExercise(
                exercise_id=exercise.id,
                order_index=1,
                sets=3,
                reps_min=8,
                reps_max=12,
                rest_seconds=90,
                rir=2,
                estimated_minutes=5,
                exercise_snapshot={},
            )
        )
        plan.days.append(day)
    db.add(plan)
    db.flush()
    cycle = WorkoutCycle(
        user_id=user_id,
        workout_plan_id=plan.id,
        duration_weeks=4,
        started_at=datetime.now(UTC) - timedelta(days=days_ago),
    )
    db.add(cycle)
    db.flush()
    return plan, cycle, plan.days[0].exercises[0]


def _payload(*, sessions_completed: int = 1, pain: bool = False) -> dict[str, object]:
    return {
        "sessions_completed": sessions_completed,
        "perceived_difficulty": "appropriate",
        "recovery_rating": "good",
        "has_pain_or_limitation": pain,
        "pain_follow_up": None,
        "note_optional": "Weekly note",
    }


def test_weekly_check_in_route_is_registered(client: TestClient) -> None:
    paths = client.app.openapi()["paths"]

    assert "/api/v1/workout-cycles/current/weekly-check-in" in paths
    assert "get" in paths["/api/v1/workout-cycles/current/weekly-check-in"]
    assert "put" in paths["/api/v1/workout-cycles/current/weekly-check-in"]


def test_get_returns_the_current_weeks_existing_check_in(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"weekly-get-{uuid4()}@example.com")
    _plan, cycle, _prescribed = _plan_with_cycle(db, user_id, days_ago=7)

    created = client.put(
        "/api/v1/workout-cycles/current/weekly-check-in",
        headers=ORIGIN,
        json=_payload(sessions_completed=1),
    )
    assert created.status_code == 200

    response = client.get("/api/v1/workout-cycles/current/weekly-check-in")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created.json()["id"]
    assert body["cycle_id"] == str(cycle.id)
    assert body["week_number"] == 2
    assert body["sessions_completed"] == 1
    assert body["pain_follow_up"] is None


def test_get_returns_404_when_current_week_has_no_check_in(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"weekly-empty-{uuid4()}@example.com")
    _plan_with_cycle(db, user_id)

    response = client.get("/api/v1/workout-cycles/current/weekly-check-in")

    assert response.status_code == 404
    assert response.json() == {"detail": "No weekly check-in for current week"}


def test_put_creates_current_weeks_check_in_without_client_week_number(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"weekly-create-{uuid4()}@example.com")
    _plan, cycle, _prescribed = _plan_with_cycle(db, user_id, days_ago=7)

    response = client.put(
        "/api/v1/workout-cycles/current/weekly-check-in",
        headers=ORIGIN,
        json=_payload(),
    )

    assert response.status_code == 200
    assert response.json()["cycle_id"] == str(cycle.id)
    assert response.json()["week_number"] == 2
    assert "week_number" not in _payload()


def test_put_updates_existing_check_in_instead_of_creating_duplicate(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"weekly-update-{uuid4()}@example.com")
    _plan, cycle, _prescribed = _plan_with_cycle(db, user_id)

    first = client.put(
        "/api/v1/workout-cycles/current/weekly-check-in",
        headers=ORIGIN,
        json=_payload(sessions_completed=0),
    )
    second = client.put(
        "/api/v1/workout-cycles/current/weekly-check-in",
        headers=ORIGIN,
        json={**_payload(sessions_completed=1), "note_optional": "Updated"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["sessions_completed"] == 1
    assert second.json()["note_optional"] == "Updated"
    assert (
        db.scalar(
            select(func.count())
            .select_from(WorkoutCycleWeeklyCheckIn)
            .where(WorkoutCycleWeeklyCheckIn.cycle_id == cycle.id)
        )
        == 1
    )


def test_put_persists_valid_pain_follow_up_from_current_plan(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"weekly-pain-valid-{uuid4()}@example.com")
    _plan, cycle, prescribed = _plan_with_cycle(db, user_id)
    payload = _payload(pain=True)
    payload["pain_follow_up"] = {
        "workout_plan_exercise_id": str(prescribed.id),
        "note_optional": "Knee discomfort",
    }

    response = client.put(
        "/api/v1/workout-cycles/current/weekly-check-in",
        headers=ORIGIN,
        json=payload,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["cycle_id"] == str(cycle.id)
    assert body["has_pain_or_limitation"] is True
    assert body["pain_follow_up"]["workout_plan_exercise_id"] == str(prescribed.id)
    assert body["pain_follow_up"]["note_optional"] == "Knee discomfort"


def test_another_users_cycle_and_check_in_are_never_returned(
    client: TestClient,
    db: Session,
) -> None:
    owner = _user(db, "weekly-owner")
    _plan_with_cycle(db, owner.id)
    _register(client, f"weekly-other-{uuid4()}@example.com")

    response = client.get("/api/v1/workout-cycles/current/weekly-check-in")

    assert response.status_code == 404
    assert response.json() == {"detail": "No active workout cycle"}


def test_invalid_sessions_are_rejected(client: TestClient, db: Session) -> None:
    user_id = _register(client, f"weekly-invalid-sessions-{uuid4()}@example.com")
    _plan_with_cycle(db, user_id, training_days=1)

    response = client.put(
        "/api/v1/workout-cycles/current/weekly-check-in",
        headers=ORIGIN,
        json=_payload(sessions_completed=2),
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Completed sessions must be within the plan's prescribed weekly days"
    }


def test_invalid_difficulty_and_recovery_are_rejected(client: TestClient, db: Session) -> None:
    user_id = _register(client, f"weekly-invalid-enums-{uuid4()}@example.com")
    _plan_with_cycle(db, user_id)
    payload = _payload()
    payload["perceived_difficulty"] = "impossible"
    payload["recovery_rating"] = "unknown"

    response = client.put(
        "/api/v1/workout-cycles/current/weekly-check-in",
        headers=ORIGIN,
        json=payload,
    )

    assert response.status_code == 422


def test_invalid_pain_reference_is_rejected(client: TestClient, db: Session) -> None:
    owner_id = _register(client, f"weekly-pain-owner-{uuid4()}@example.com")
    _plan, owner_cycle, _owner_exercise = _plan_with_cycle(db, owner_id)
    other_user = _user(db, "weekly-pain-other")
    _other_plan, _other_cycle, other_exercise = _plan_with_cycle(db, other_user.id)
    payload = _payload(pain=True)
    payload["pain_follow_up"] = {
        "workout_plan_exercise_id": str(other_exercise.id),
        "note_optional": "Pain",
    }

    response = client.put(
        "/api/v1/workout-cycles/current/weekly-check-in",
        headers=ORIGIN,
        json=payload,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Workout plan exercise not found in current cycle"}
    assert owner_cycle.user_id == owner_id


def test_put_returns_404_without_an_active_cycle(client: TestClient) -> None:
    _register(client, f"weekly-no-cycle-{uuid4()}@example.com")

    response = client.put(
        "/api/v1/workout-cycles/current/weekly-check-in",
        headers=ORIGIN,
        json=_payload(),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "No active workout cycle"}
