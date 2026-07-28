import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.ai.fake_provider import FakeWorkoutPlanModelProvider
from app.ai.schemas import (
    WorkoutGenerationModelResponse,
    WorkoutPlanDayOutput,
    WorkoutPlanExerciseOutput,
    WorkoutPlanModelOutput,
)
from app.auth.models import User
from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    Equipment,
    ExerciseType,
    MediaType,
    MovementPattern,
    MuscleGroup,
)
from app.exercises.models import Exercise, ExerciseEquipment
from app.profile.enums import ExperienceLevel, FitnessGoal, HomeTrainingSetup, Sex, TrainingLocation
from app.profile.models import BodyMeasurement, UserProfile
from app.workouts.enums import WorkoutGenerationStatus, WorkoutPlanStatus
from app.workouts.models import WorkoutPlan, WorkoutPlanGeneration
from app.workouts.repository import create_generation
from app.workouts.service import (
    GenerationCooldownError,
    GenerationInProgressError,
    WorkoutGenerationFailedError,
    WorkoutGenerationService,
    WorkoutGenerationSettings,
)


def _user_with_profile(db: Session) -> User:
    user = User(email="workout-service@example.com", password_hash="hash")
    db.add(user)
    db.flush()
    db.add(
        UserProfile(
            user_id=user.id,
            display_name="Athlete",
            birth_date=date(1997, 1, 1),
            sex=Sex.MALE,
            height_cm=180,
            fitness_goal=FitnessGoal.BUILD_MUSCLE,
            experience_level=ExperienceLevel.BEGINNER,
            training_days_per_week=1,
            training_location=TrainingLocation.HOME,
            home_training_setup=HomeTrainingSetup.BODYWEIGHT_ONLY,
            session_duration_minutes=45,
            plan_duration_weeks=4,
        )
    )
    db.add(BodyMeasurement(user_id=user.id, weight_kg=Decimal("75")))
    db.flush()
    return user


def _exercise(db: Session, slug: str, pattern: MovementPattern, muscle: MuscleGroup) -> Exercise:
    item = Exercise(
        slug=slug,
        name_en=slug,
        name_fa=slug,
        body_region=BodyRegion.UPPER_BODY,
        primary_muscle=muscle,
        difficulty=Difficulty.BEGINNER,
        movement_pattern=pattern,
        exercise_type=ExerciseType.COMPOUND,
        instructions_en=["one", "two", "three"],
        instructions_fa=["یک", "دو", "سه"],
        safety_notes_en=["steady"],
        safety_notes_fa=["آرام"],
        media_path="placeholder.webp",
        media_type=MediaType.PLACEHOLDER,
        is_active=True,
        is_programmable=True,
        equipment_items=[ExerciseEquipment(equipment=Equipment.BODYWEIGHT)],
    )
    db.add(item)
    db.flush()
    return item


def _seed_candidates(db: Session) -> list[Exercise]:
    return [
        _exercise(db, "service-push", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
        _exercise(db, "service-pull", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        _exercise(db, "service-squat", MovementPattern.SQUAT, MuscleGroup.QUADRICEPS),
    ]


def _response(exercise_ids: list[UUID]) -> WorkoutGenerationModelResponse:
    return WorkoutGenerationModelResponse(
        plan=WorkoutPlanModelOutput(
            days=[
                WorkoutPlanDayOutput(
                    day_number=1,
                    title_en="Full body",
                    title_fa="تمام بدن",
                    estimated_duration_minutes=24,
                    exercises=[
                        WorkoutPlanExerciseOutput(
                            exercise_id=exercise_id,
                            sets=3,
                            reps_min=8,
                            reps_max=12,
                            rest_seconds=90,
                            rir=2,
                            estimated_minutes=8,
                        )
                        for exercise_id in exercise_ids
                    ],
                )
            ]
        ),
        provider_request_id="response-id",
        input_tokens=10,
        output_tokens=20,
    )


def _service(
    db: Session,
    provider: FakeWorkoutPlanModelProvider,
    *,
    cooldown_seconds: int = 0,
) -> WorkoutGenerationService:
    return WorkoutGenerationService(
        db,
        provider=provider,
        settings=WorkoutGenerationSettings(
            provider_name="fake",
            model_id="fake-model",
            prompt_version="v1",
            generation_policy_version="v1",
            catalog_programming_version="v1",
            max_repair_attempts=1,
            cooldown_seconds=cooldown_seconds,
            max_candidates=80,
            max_request_bytes=262144,
            warmup_minutes=5,
        ),
    )


def test_generation_persists_valid_plan_then_reuses_same_signature(db: Session) -> None:
    user = _user_with_profile(db)
    exercises = _seed_candidates(db)
    provider = FakeWorkoutPlanModelProvider([_response([item.id for item in exercises])])
    service = _service(db, provider)

    first = asyncio.run(service.generate(user.id))
    second = asyncio.run(service.generate(user.id))

    assert not first.reused
    assert second.reused
    assert second.plan.id == first.plan.id
    assert len(provider.calls) == 1
    assert first.plan.status is WorkoutPlanStatus.ACTIVE
    assert first.plan.generation_records[0].input_tokens == 10


def test_invalid_response_is_repaired_once_before_persistence(db: Session) -> None:
    user = _user_with_profile(db)
    exercises = _seed_candidates(db)
    invalid = _response([exercises[0].id, exercises[0].id])
    provider = FakeWorkoutPlanModelProvider([invalid, _response([item.id for item in exercises])])

    result = asyncio.run(_service(db, provider).generate(user.id))

    assert not result.reused
    assert len(provider.calls) == 2
    assert "repair" in provider.calls[1].input_payload


def test_failed_replacement_preserves_previous_active_plan(db: Session) -> None:
    user = _user_with_profile(db)
    exercises = _seed_candidates(db)
    initial = asyncio.run(
        _service(
            db, FakeWorkoutPlanModelProvider([_response([item.id for item in exercises])])
        ).generate(user.id)
    )
    profile = db.get(UserProfile, user.id)
    assert profile is not None
    profile.fitness_goal = FitnessGoal.IMPROVE_FITNESS
    db.commit()
    invalid = _response([exercises[0].id, exercises[0].id])

    with pytest.raises(WorkoutGenerationFailedError):
        asyncio.run(
            _service(db, FakeWorkoutPlanModelProvider([invalid, invalid])).generate(user.id)
        )

    assert db.get(WorkoutPlan, initial.plan.id).status is WorkoutPlanStatus.ACTIVE  # type: ignore[union-attr]


def test_generation_in_progress_rejects_a_second_request(db: Session) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)
    create_generation(
        db,
        user_id=user.id,
        provider="fake",
        model_id="fake-model",
        candidate_count=3,
    )
    db.commit()

    with pytest.raises(GenerationInProgressError):
        asyncio.run(_service(db, FakeWorkoutPlanModelProvider([])).generate(user.id))

    generation = db.query(WorkoutPlan).filter_by(user_id=user.id).first()
    assert generation is None
    assert db.query(WorkoutPlan).count() == 0


def test_expired_active_plan_is_replaced_instead_of_reused(db: Session) -> None:
    user = _user_with_profile(db)
    exercises = _seed_candidates(db)
    first = asyncio.run(
        _service(
            db, FakeWorkoutPlanModelProvider([_response([item.id for item in exercises])])
        ).generate(user.id)
    )
    first.plan.activated_at = datetime.now(UTC) - timedelta(days=29)
    db.commit()

    provider = FakeWorkoutPlanModelProvider([_response([item.id for item in exercises])])
    replacement = asyncio.run(_service(db, provider).generate(user.id))

    assert not replacement.reused
    assert replacement.plan.id != first.plan.id
    assert len(provider.calls) == 1
    assert db.get(WorkoutPlan, first.plan.id).status is WorkoutPlanStatus.SUPERSEDED  # type: ignore[union-attr]


def test_active_plan_reports_stale_when_generation_conditions_change(db: Session) -> None:
    user = _user_with_profile(db)
    exercises = _seed_candidates(db)
    asyncio.run(
        _service(
            db, FakeWorkoutPlanModelProvider([_response([item.id for item in exercises])])
        ).generate(user.id)
    )
    profile = db.get(UserProfile, user.id)
    assert profile is not None
    profile.fitness_goal = FitnessGoal.IMPROVE_FITNESS
    db.commit()
    provider = FakeWorkoutPlanModelProvider([])

    active = _service(db, provider).get_active(user.id)

    assert active is not None
    assert active.is_stale
    assert provider.calls == []


def test_profile_change_during_provider_call_prevents_activation(db: Session) -> None:
    user = _user_with_profile(db)
    exercises = _seed_candidates(db)

    class ProfileMutatingProvider(FakeWorkoutPlanModelProvider):
        async def generate_plan(self, request: object) -> WorkoutGenerationModelResponse:
            profile = db.get(UserProfile, user.id)
            assert profile is not None
            profile.fitness_goal = FitnessGoal.IMPROVE_FITNESS
            return await super().generate_plan(request)  # type: ignore[arg-type]

    with pytest.raises(WorkoutGenerationFailedError):
        asyncio.run(
            _service(
                db,
                ProfileMutatingProvider([_response([item.id for item in exercises])]),
            ).generate(user.id)
        )

    assert db.query(WorkoutPlan).filter_by(user_id=user.id).count() == 0
    generation = db.query(WorkoutPlanGeneration).filter_by(user_id=user.id).one()
    assert generation.status is WorkoutGenerationStatus.FAILED
    assert generation.error_code == "generation_inputs_changed"


def test_generation_cooldown_prevents_another_provider_request(db: Session) -> None:
    user = _user_with_profile(db)
    exercises = _seed_candidates(db)
    first_provider = FakeWorkoutPlanModelProvider([_response([item.id for item in exercises])])
    asyncio.run(_service(db, first_provider, cooldown_seconds=300).generate(user.id))
    profile = db.get(UserProfile, user.id)
    assert profile is not None
    profile.fitness_goal = FitnessGoal.IMPROVE_FITNESS
    db.commit()
    second_provider = FakeWorkoutPlanModelProvider([])

    with pytest.raises(GenerationCooldownError) as error:
        asyncio.run(_service(db, second_provider, cooldown_seconds=300).generate(user.id))

    assert 1 <= error.value.retry_after_seconds <= 300
    assert second_provider.calls == []
