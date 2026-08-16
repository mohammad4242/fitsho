from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai.schemas import ProviderErrorCode
from app.exercises.enums import BodyRegion, Difficulty, MediaType, MuscleGroup
from app.exercises.models import Exercise, ExerciseAlternative
from app.exercises.taxonomy import FOCUSES_BY_MUSCLE
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanExercise
from app.workouts.schemas import ProgramGenerationOverrides
from app.workouts.service import (
    GenerationCooldownError,
    ProgramGenerationRejectedError,
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


def _exercise(
    slug: str,
    *,
    is_active: bool = True,
    muscle: MuscleGroup = MuscleGroup.CHEST,
) -> Exercise:
    unique_slug = f"{slug}-{uuid4().hex}"
    return Exercise(
        slug=unique_slug,
        name_en=unique_slug.replace("-", " ").title(),
        name_fa=f"حرکت {unique_slug}",
        body_region=BodyRegion.UPPER_BODY,
        primary_muscle=muscle,
        muscle_focus=next(iter(FOCUSES_BY_MUSCLE[muscle]), None),
        difficulty=Difficulty.BEGINNER,
        instructions_en=["Set up.", "Perform the movement.", "Finish safely."],
        instructions_fa=["شروع کن.", "حرکت را انجام بده.", "ایمن تمام کن."],
        safety_notes_en=["Move with control."],
        safety_notes_fa=["کنترل‌شده حرکت کن."],
        media_path="/exercises/exercise-placeholder.svg",
        media_type=MediaType.PLACEHOLDER,
        is_active=is_active,
    )


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


def test_workout_plan_pdf_requires_authentication(client: TestClient) -> None:
    assert client.get(f"/api/v1/workout-plans/{uuid4()}/pdf").status_code == 401


def test_workout_plan_pdf_is_scoped_to_its_owner(client: TestClient, db: Session) -> None:
    owner_id = _register_and_complete_profile(client, "pdf-owner@example.com")
    plan = _plan(db, owner_id)
    exercise = _exercise("pdf-bench-press")
    day = WorkoutDay(
        workout_plan=plan,
        day_number=1,
        title_en="Upper body",
        title_fa="بالاتنه",
        estimated_duration_minutes=30,
        ai_coach_explanation_fa="حرکت‌ها را کنترل‌شده اجرا کن.",
    )
    db.add_all(
        [
            exercise,
            day,
            WorkoutPlanExercise(
                workout_day=day,
                exercise=exercise,
                order_index=1,
                sets=3,
                reps_min=8,
                reps_max=12,
                rest_seconds=90,
                rir=2,
                estimated_minutes=8,
                notes_fa="فرم صحیح را حفظ کن.",
            ),
        ]
    )
    db.commit()

    response = client.get(f"/api/v1/workout-plans/{plan.id}/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.content.startswith(b"%PDF-")

    assert client.post("/api/v1/auth/logout", headers=ORIGIN).status_code == 204
    _register_and_complete_profile(client, "pdf-other@example.com")

    assert client.get(f"/api/v1/workout-plans/{plan.id}/pdf").status_code == 404


def test_workout_plan_returns_active_curated_alternatives_read_only(
    client: TestClient, db: Session
) -> None:
    user_id = _register_and_complete_profile(client, "alternatives-plan@example.com")
    plan = _plan(db, user_id)
    planned = _exercise("dumbbell-bench-press")
    active_alternative = _exercise("push-up")
    inactive_alternative = _exercise("inactive-chest-press", is_active=False)
    day = WorkoutDay(
        workout_plan=plan,
        day_number=1,
        title_en="Upper body",
        title_fa="بالاتنه",
        estimated_duration_minutes=30,
    )
    db.add_all(
        [
            planned,
            active_alternative,
            inactive_alternative,
            day,
            WorkoutPlanExercise(
                workout_day=day,
                exercise=planned,
                order_index=1,
                sets=3,
                reps_min=8,
                reps_max=12,
                rest_seconds=90,
                rir=2,
                estimated_minutes=8,
            ),
            ExerciseAlternative(
                exercise=planned,
                alternative_exercise=active_alternative,
                reason_en="A no-equipment alternative.",
                reason_fa="جایگزین بدون تجهیزات.",
            ),
            ExerciseAlternative(
                exercise=planned,
                alternative_exercise=inactive_alternative,
                reason_en="Inactive catalog item.",
                reason_fa="حرکت غیرفعال.",
            ),
        ]
    )
    db.commit()

    response = client.get(f"/api/v1/workout-plans/{plan.id}")

    assert response.status_code == 200
    alternatives = response.json()["days"][0]["exercises"][0]["alternatives"]
    assert alternatives == [
        {
            "reason_en": "A no-equipment alternative.",
            "reason_fa": "جایگزین بدون تجهیزات.",
            "exercise": {
                "id": str(active_alternative.id),
                "slug": active_alternative.slug,
                "name_en": active_alternative.name_en,
                "name_fa": active_alternative.name_fa,
                "content_type": "exercise",
                "body_region": "upper_body",
                "primary_muscle": "chest",
                "muscle_focus": "general_chest",
                "labels": [],
                "secondary_muscles": [],
                "equipment": [],
                "difficulty": "beginner",
                "media_path": "/exercises/exercise-placeholder.svg",
                "media_type": "placeholder",
            },
        }
    ]


def test_deterministic_plan_response_derives_titles_from_direct_targets(
    client: TestClient, db: Session
) -> None:
    user_id = _register_and_complete_profile(client, "direct-target-titles@example.com")
    plan = _plan(db, user_id)
    plan.engine_version = "program_engine_v1"
    chest = _exercise("direct-chest", muscle=MuscleGroup.CHEST)
    triceps = _exercise("direct-triceps", muscle=MuscleGroup.TRICEPS)
    day = WorkoutDay(
        workout_plan=plan,
        day_number=1,
        title_en="Upper body",
        title_fa="بالاتنه",
        estimated_duration_minutes=30,
    )
    db.add_all(
        [
            chest,
            triceps,
            day,
            WorkoutPlanExercise(
                workout_day=day,
                exercise=chest,
                order_index=1,
                sets=3,
                reps_min=8,
                reps_max=12,
                rest_seconds=90,
                rir=2,
                estimated_minutes=8,
            ),
            WorkoutPlanExercise(
                workout_day=day,
                exercise=triceps,
                order_index=2,
                sets=2,
                reps_min=10,
                reps_max=15,
                rest_seconds=60,
                rir=2,
                estimated_minutes=6,
            ),
        ]
    )
    db.commit()

    response = client.get(f"/api/v1/workout-plans/{plan.id}")

    assert response.status_code == 200
    assert response.json()["days"][0]["title_en"] == "Day 1: Chest + Triceps"
    assert response.json()["days"][0]["title_fa"] == "روز 1: سینه + پشت بازو"


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


def test_generate_accepts_typed_optional_engine_evidence(client: TestClient, db: Session) -> None:
    user_id = _register_and_complete_profile(client, "generate-overrides@example.com")
    plan = _plan(db, user_id)
    captured_seed: list[int | None] = []

    class FakeService:
        async def generate(
            self,
            current_user_id: UUID,
            payload: ProgramGenerationOverrides,
        ) -> WorkoutPlanGenerationResult:
            assert current_user_id == user_id
            captured_seed.append(payload.seed_optional)
            return WorkoutPlanGenerationResult(plan=plan, reused=False)

    from app.workouts.dependencies import get_workout_generation_service

    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_workout_generation_service] = lambda: FakeService()
    response = client.post(
        "/api/v1/workout-plans/generate",
        headers=ORIGIN,
        json={"seed_optional": 123, "priority_muscles": ["back"]},
    )
    app.dependency_overrides.pop(get_workout_generation_service)

    assert response.status_code == 200
    assert captured_seed == [123]


def test_generate_returns_structured_professional_review_status(client: TestClient) -> None:
    _register_and_complete_profile(client, "review-plan@example.com")

    class FakeService:
        async def generate(self, current_user_id: UUID) -> WorkoutPlanGenerationResult:
            raise ProgramGenerationRejectedError("PROGRAM_REJECTED_SAFETY_STATUS", "stop_and_refer")

    from app.workouts.dependencies import get_workout_generation_service

    app = cast(FastAPI, client.app)
    app.dependency_overrides[get_workout_generation_service] = lambda: FakeService()
    response = client.post("/api/v1/workout-plans/generate", headers=ORIGIN)
    app.dependency_overrides.pop(get_workout_generation_service)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "PROGRAM_REJECTED_SAFETY_STATUS"
    assert response.json()["detail"]["safety_status"] == "stop_and_refer"


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
