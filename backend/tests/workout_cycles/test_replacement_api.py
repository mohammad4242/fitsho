from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
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
from app.workout_cycles.enums import WorkoutCycleStatus
from app.workout_cycles.models import WorkoutCycle, WorkoutPlanExercise
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutDay, WorkoutPlan

ORIGIN = {"Origin": "http://localhost:5173"}


def _register(client: TestClient, email: str) -> UUID:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def _user(db: Session) -> User:
    user = User(email=f"replacement-api-{uuid4()}@example.com", password_hash="hash")
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
    plan_status: WorkoutPlanStatus = WorkoutPlanStatus.ACTIVE,
    create_cycle: bool = True,
    days_ago: int = 7,
) -> tuple[WorkoutPlan, WorkoutPlanExercise, WorkoutCycle | None, Exercise, Exercise, Exercise]:
    original = _exercise(db, "api-original")
    safe_alternative = _exercise(db, "api-safe-alternative")
    unsafe_alternative = _exercise(db, "api-unsafe-alternative")
    plan = WorkoutPlan(
        user_id=user_id,
        status=plan_status,
        generation_signature="a" * 64,
        profile_snapshot={"plan_duration_weeks": 4},
        provider="fake",
        model_id="fake-model",
        prompt_version="v1",
        generation_policy_version="v1",
        candidate_set_hash="b" * 64,
        generation_method="coach_review",
    )
    day = WorkoutDay(
        day_number=1,
        title_en="Upper body",
        title_fa="بالاتنه",
        estimated_duration_minutes=20,
    )
    prescribed = WorkoutPlanExercise(
        exercise_id=original.id,
        order_index=1,
        sets=3,
        reps_min=8,
        reps_max=12,
        rest_seconds=90,
        rir=2,
        estimated_minutes=5,
        exercise_snapshot={},
        substitution_exercise_ids=[str(safe_alternative.id)],
    )
    day.exercises.append(prescribed)
    plan.days.append(day)
    db.add(plan)
    db.flush()
    cycle = None
    if create_cycle:
        cycle = WorkoutCycle(
            user_id=user_id,
            workout_plan_id=plan.id,
            duration_weeks=4,
            status=WorkoutCycleStatus.ACTIVE,
            started_at=datetime.now(UTC) - timedelta(days=days_ago),
        )
        db.add(cycle)
        db.flush()
    return plan, prescribed, cycle, original, safe_alternative, unsafe_alternative


def _payload(prescribed: WorkoutPlanExercise, replacement: Exercise) -> dict[str, str]:
    return {
        "workout_plan_exercise_id": str(prescribed.id),
        "replacement_exercise_id": str(replacement.id),
        "reason": "equipment_unavailable",
        "scope": "this_time",
    }


def test_valid_replacement_is_recorded_with_server_cycle_and_week(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"valid-replacement-{uuid4()}@example.com")
    plan, prescribed, cycle, original, safe, _unsafe = _plan_with_cycle(db, user_id)
    assert cycle is not None

    response = client.post(
        "/api/v1/workout-cycles/current/replacements",
        headers=ORIGIN,
        json=_payload(prescribed, safe),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == str(user_id)
    assert body["cycle_id"] == str(cycle.id)
    assert body["workout_plan_exercise_id"] == str(prescribed.id)
    assert body["original_exercise_id"] == str(original.id)
    assert body["replacement_exercise_id"] == str(safe.id)
    assert body["reason"] == "equipment_unavailable"
    assert body["scope"] == "this_time"
    assert body["week_number"] == 2
    assert body["created_at"] is not None
    assert cycle.workout_plan_id == plan.id


def test_replacement_rejects_another_users_plan_exercise(
    client: TestClient,
    db: Session,
) -> None:
    owner_id = _user(db).id
    _plan, owner_item, _owner_cycle, _original, owner_safe, _unsafe = _plan_with_cycle(db, owner_id)
    client_user_id = _register(client, f"other-member-{uuid4()}@example.com")
    _plan_with_cycle(db, client_user_id)

    response = client.post(
        "/api/v1/workout-cycles/current/replacements",
        headers=ORIGIN,
        json=_payload(owner_item, owner_safe),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Workout plan exercise not found in current cycle"}


def test_replacement_rejects_exercise_outside_current_active_cycle(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"outside-cycle-{uuid4()}@example.com")
    _plan, _current_item, _cycle, _original, _safe, _unsafe = _plan_with_cycle(db, user_id)
    (
        _outside_plan,
        outside_item,
        _outside_cycle,
        _outside_original,
        outside_safe,
        _outside_unsafe,
    ) = _plan_with_cycle(
        db,
        user_id,
        plan_status=WorkoutPlanStatus.SUPERSEDED,
        create_cycle=False,
    )

    response = client.post(
        "/api/v1/workout-cycles/current/replacements",
        headers=ORIGIN,
        json=_payload(outside_item, outside_safe),
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Workout plan exercise not found in current cycle"}


def test_replacement_must_be_a_safe_attached_alternative(
    client: TestClient,
    db: Session,
) -> None:
    user_id = _register(client, f"unsafe-alternative-{uuid4()}@example.com")
    _plan, prescribed, _cycle, _original, _safe, unsafe = _plan_with_cycle(db, user_id)

    response = client.post(
        "/api/v1/workout-cycles/current/replacements",
        headers=ORIGIN,
        json=_payload(prescribed, unsafe),
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Replacement exercise is not an allowed alternative"}


def test_self_replacement_is_rejected(client: TestClient, db: Session) -> None:
    user_id = _register(client, f"self-replacement-{uuid4()}@example.com")
    _plan, prescribed, _cycle, original, _safe, _unsafe = _plan_with_cycle(db, user_id)

    response = client.post(
        "/api/v1/workout-cycles/current/replacements",
        headers=ORIGIN,
        json=_payload(prescribed, original),
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Replacement exercise must differ from original exercise"}


def test_replacement_requires_an_active_cycle(client: TestClient) -> None:
    _register(client, f"no-active-cycle-replacement-{uuid4()}@example.com")

    response = client.post(
        "/api/v1/workout-cycles/current/replacements",
        headers=ORIGIN,
        json={
            "workout_plan_exercise_id": str(uuid4()),
            "replacement_exercise_id": str(uuid4()),
            "reason": "other",
            "scope": "persistent",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "No active workout cycle"}


@pytest.mark.parametrize(
    ("field", "value"),
    [("reason", "not-a-reason"), ("scope", "not-a-scope")],
)
def test_replacement_rejects_invalid_reason_and_scope_schema_values(
    client: TestClient,
    db: Session,
    field: str,
    value: str,
) -> None:
    user_id = _register(client, f"invalid-replacement-input-{uuid4()}@example.com")
    _plan, prescribed, _cycle, _original, safe, _unsafe = _plan_with_cycle(db, user_id)
    payload = _payload(prescribed, safe)
    payload[field] = value

    response = client.post(
        "/api/v1/workout-cycles/current/replacements",
        headers=ORIGIN,
        json=payload,
    )

    assert response.status_code == 422
