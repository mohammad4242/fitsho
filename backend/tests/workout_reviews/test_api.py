from __future__ import annotations

from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.body_analysis.enums import SpecialistRole
from app.body_analysis.models import UserSpecialistRole
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
from app.workout_reviews.repository import ensure_pending_review
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanExercise

ORIGIN = {"Origin": "http://localhost:5173"}
PROFILE = {
    "display_name": "History Member",
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


def _register(client: TestClient, email: str) -> UUID:
    response = client.post(
        "/api/v1/auth/register",
        headers=ORIGIN,
        json={"email": email, "password": "long password"},
    )
    assert response.status_code == 201
    return UUID(response.json()["id"])


def _switch_user(client: TestClient, email: str) -> UUID:
    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204
    return _register(client, email)


def _plan(db: Session, user_id: UUID) -> WorkoutPlan:
    exercise = Exercise(
        slug=f"coach-api-{uuid4().hex}",
        name_en="Chest Press",
        name_fa="پرس سینه",
        body_region=BodyRegion.UPPER_BODY,
        primary_muscle=MuscleGroup.CHEST,
        muscle_focus=MuscleFocus.MID_CHEST,
        difficulty=Difficulty.BEGINNER,
        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
        exercise_type=ExerciseType.COMPOUND,
        instructions_en=["Set up.", "Press.", "Return."],
        instructions_fa=["آماده شو.", "پرس کن.", "برگرد."],
        safety_notes_en=["Control the weight."],
        safety_notes_fa=["وزنه را کنترل کن."],
        media_path="/exercises/exercise-placeholder.svg",
        media_type=MediaType.PLACEHOLDER,
        is_active=True,
        is_programmable=True,
    )
    db.add(exercise)
    db.flush()
    snapshot = {
        "id": str(exercise.id),
        "primary_muscle": "chest",
        "secondary_muscles": [],
        "movement_pattern": "horizontal_push",
        "exercise_type": "compound",
        "equipment": [],
        "difficulty": "beginner",
        "caution_tags": [],
        "labels": [],
    }
    plan = WorkoutPlan(
        user_id=user_id,
        status=WorkoutPlanStatus.ACTIVE,
        generation_signature="a" * 64,
        profile_snapshot={
            "plan_duration_weeks": 4,
            "session_duration_minutes": 45,
            "goal": "build_muscle",
            "experience_level": "beginner",
        },
        provider="fake",
        model_id="fake-model",
        prompt_version="v1",
        generation_policy_version="v1",
        candidate_set_hash="b" * 64,
        generation_method="ai",
        exercise_catalog_snapshot={"exercises": {str(exercise.id): snapshot}},
    )
    day = WorkoutDay(
        day_number=1,
        title_en="Upper body",
        title_fa="بالاتنه",
        estimated_duration_minutes=20,
    )
    day.exercises.append(
        WorkoutPlanExercise(
            exercise=exercise,
            order_index=1,
            sets=3,
            reps_min=8,
            reps_max=12,
            rest_seconds=90,
            rir=2,
            estimated_minutes=5,
            exercise_snapshot=snapshot,
        )
    )
    plan.days.append(day)
    db.add(plan)
    db.flush()
    return plan


def test_member_cannot_read_coach_queue(client: TestClient) -> None:
    _register(client, f"member-{uuid4()}@example.com")

    response = client.get("/api/v1/coach/workout-reviews")

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "COACH_ROLE_REQUIRED"


def test_member_workout_response_hides_internal_decision_trace(
    client: TestClient,
    db: Session,
) -> None:
    member_id = _register(client, f"private-trace-{uuid4()}@example.com")
    assert client.post("/api/v1/profile", headers=ORIGIN, json=PROFILE).status_code == 201
    plan = _plan(db, member_id)
    plan.decision_trace = [
        {
            "stage": "template_selection",
            "selected": "private-template",
            "candidates": [{"slug": "private-template", "score": {"total": 100}}],
        }
    ]
    db.commit()

    response = client.get(f"/api/v1/workout-plans/{plan.id}")

    assert response.status_code == 200
    assert "decision_trace" not in response.json()
    assert "private-template" not in response.text


def test_coach_lists_and_claims_pending_review(client: TestClient, db: Session) -> None:
    member_id = _register(client, f"queue-member-{uuid4()}@example.com")
    review = ensure_pending_review(db, _plan(db, member_id))
    db.commit()
    coach_id = _switch_user(client, f"queue-coach-{uuid4()}@example.com")
    db.add(UserSpecialistRole(user_id=coach_id, role=SpecialistRole.COACH))
    db.commit()

    access = client.get("/api/v1/coach/workout-reviews/access")
    queue = client.get("/api/v1/coach/workout-reviews?view=pending")
    claimed = client.post(
        f"/api/v1/coach/workout-reviews/{review.id}/claim",
        headers=ORIGIN,
    )

    assert access.status_code == 200
    assert access.json() == {"authorized": True}
    assert queue.status_code == 200
    assert [item["id"] for item in queue.json()] == [str(review.id)]
    assert claimed.status_code == 200
    assert claimed.json()["status"] == "claimed"
    assert claimed.json()["draft_revision"] == 1


def test_coach_detail_projects_selected_template_without_full_trace(
    client: TestClient,
    db: Session,
) -> None:
    member_id = _register(client, f"template-member-{uuid4()}@example.com")
    plan = _plan(db, member_id)
    plan.decision_trace = [
        {
            "stage": "template_selection",
            "requested_days": 4,
            "experience_level": "intermediate",
            "templates_considered": 2,
            "hard_rejections": [],
            "candidates": [
                {
                    "slug": "four-day-strength",
                    "score": {
                        "priority": 100,
                        "body_analysis": 0,
                        "goal": 25,
                        "sex": 0,
                        "fallback": 0,
                        "total": 125,
                    },
                    "reason_codes": [
                        "EXPLICIT_PRIORITY_EXACT_MATCH",
                        "GOAL_STRENGTH_BIAS_MATCH",
                    ],
                }
            ],
            "selected": "four-day-strength",
            "tie_break": None,
        }
    ]
    review = ensure_pending_review(db, plan)
    db.commit()
    coach_id = _switch_user(client, f"template-coach-{uuid4()}@example.com")
    db.add(UserSpecialistRole(user_id=coach_id, role=SpecialistRole.COACH))
    db.commit()

    response = client.get(f"/api/v1/coach/workout-reviews/{review.id}")

    assert response.status_code == 200
    payload = response.json()
    assert "decision_trace" not in payload["source_plan"]
    assert payload["template_selection"] == {
        "selected_template": "four-day-strength",
        "explanation_fa": payload["template_selection"]["explanation_fa"],
        "explanation_en": payload["template_selection"]["explanation_en"],
        "score": {
            "priority": 100,
            "body_analysis": 0,
            "goal": 25,
            "sex": 0,
            "fallback": 0,
            "total": 125,
        },
    }
    assert "اولویت عضلانی صریح" in payload["template_selection"]["explanation_fa"]


def test_coach_review_detail_includes_safe_athlete_summary(
    client: TestClient,
    db: Session,
) -> None:
    member_id = _register(client, f"summary-member-{uuid4()}@example.com")
    previous = _plan(db, member_id)
    previous.status = WorkoutPlanStatus.SUPERSEDED
    db.flush()
    source = _plan(db, member_id)
    source.status = WorkoutPlanStatus.PENDING_REVIEW
    source.previous_program_id = previous.id
    db.flush()
    review = ensure_pending_review(db, source)
    db.commit()
    coach_id = _switch_user(client, f"summary-coach-{uuid4()}@example.com")
    db.add(UserSpecialistRole(user_id=coach_id, role=SpecialistRole.COACH))
    db.commit()

    response = client.get(f"/api/v1/coach/workout-reviews/{review.id}")

    assert response.status_code == 200
    summary = response.json()["athlete_summary"]
    assert summary["previous_approved_plan_id"] == str(previous.id)
    assert summary["athlete_state"]["user_id"] == str(member_id)
    assert summary["athlete_state"]["adherence"]["percent"] is None
    assert summary["athlete_state"]["recovery_trend"]["summary"] == "unknown"
    assert summary["athlete_state"]["difficulty_trend"]["summary"] == "unknown"
    assert summary["athlete_state"]["provenance"]["profile_user_id"] is None
    recommendation = response.json()["fitsho_recommendation"]
    assert recommendation["overall_action"] == "maintain"
    assert "INSUFFICIENT_RELIABLE_EVIDENCE" in recommendation["reason_codes"]
    assert recommendation["difference_summary"] == []


def test_member_history_keeps_generated_and_coach_approved_versions(
    client: TestClient,
    db: Session,
) -> None:
    member_id = _register(client, f"history-member-{uuid4()}@example.com")
    assert client.post("/api/v1/profile", headers=ORIGIN, json=PROFILE).status_code == 201
    source = _plan(db, member_id)
    review = ensure_pending_review(db, source)
    review.status = "approved"
    approved = WorkoutPlan(
        user_id=member_id,
        status=WorkoutPlanStatus.ACTIVE,
        generation_signature=source.generation_signature,
        profile_snapshot=source.profile_snapshot,
        provider=source.provider,
        model_id=source.model_id,
        prompt_version=source.prompt_version,
        generation_policy_version=source.generation_policy_version,
        candidate_set_hash=source.candidate_set_hash,
        generation_method="coach_review",
        previous_program_id=source.id,
    )
    source.status = WorkoutPlanStatus.SUPERSEDED
    db.add(approved)
    db.flush()
    review.approved_plan_id = approved.id
    db.commit()

    response = client.get("/api/v1/workout-plans/history")

    assert response.status_code == 200
    assert {item["id"] for item in response.json()} == {str(source.id), str(approved.id)}
    states = {item["id"]: item["coach_review"]["state"] for item in response.json()}
    assert states[str(source.id)] == "initial_generated"
    assert states[str(approved.id)] == "coach_approved"
