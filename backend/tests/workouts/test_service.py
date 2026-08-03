import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.ai.fake_provider import FakeWorkoutPlanModelProvider
from app.ai.routing import ModelProviderCandidate
from app.auth.models import User
from app.body_analysis.enums import BodyAnalysisStatus
from app.body_analysis.models import BodyAnalysis
from app.body_photos.enums import BodyPhotoPurpose, BodyPhotoSessionState
from app.body_photos.models import BodyPhotoSession
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
from app.workouts.body_analysis_resolver import BodyAnalysisInfluenceResolver
from app.workouts.enums import WorkoutGenerationStatus, WorkoutPlanStatus
from app.workouts.models import WorkoutPlan, WorkoutPlanGeneration
from app.workouts.program_engine.enums import GenerationErrorCode, RedFlag
from app.workouts.program_engine.schemas import BodyAnalysisInfluence, ProgramGenerationResult
from app.workouts.repository import create_generation, get_plan_for_user
from app.workouts.router import to_plan_response
from app.workouts.schemas import ProgramGenerationOverrides
from app.workouts.service import (
    GenerationCooldownError,
    GenerationInProgressError,
    NoEligibleExercisesError,
    ProgramGenerationRejectedError,
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
            training_days_per_week=2,
            training_location=TrainingLocation.HOME,
            home_training_setup=HomeTrainingSetup.BODYWEIGHT_ONLY,
            session_duration_minutes=45,
            plan_duration_weeks=4,
        )
    )
    db.add(BodyMeasurement(user_id=user.id, weight_kg=Decimal("75")))
    db.flush()
    return user


def _exercise(
    db: Session,
    slug: str,
    pattern: MovementPattern,
    muscle: MuscleGroup,
    *,
    body_region: BodyRegion = BodyRegion.UPPER_BODY,
    exercise_type: ExerciseType = ExerciseType.COMPOUND,
) -> Exercise:
    item = Exercise(
        slug=slug,
        name_en=slug,
        name_fa=slug,
        body_region=body_region,
        primary_muscle=muscle,
        difficulty=Difficulty.BEGINNER,
        movement_pattern=pattern,
        exercise_type=exercise_type,
        instructions_en=["one", "two", "three"],
        instructions_fa=["یک", "دو", "سه"],
        safety_notes_en=["steady"],
        safety_notes_fa=["آرام"],
        media_path="placeholder.webp",
        media_type=MediaType.PLACEHOLDER,
        is_active=True,
        is_programmable=True,
        needs_review=False,
        equipment_items=[ExerciseEquipment(equipment=Equipment.BODYWEIGHT)],
    )
    db.add(item)
    db.flush()
    return item


def _seed_candidates(db: Session) -> list[Exercise]:
    return [
        _exercise(db, "service-push", MovementPattern.HORIZONTAL_PUSH, MuscleGroup.CHEST),
        _exercise(db, "service-pull", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        _exercise(
            db,
            "service-squat",
            MovementPattern.SQUAT,
            MuscleGroup.QUADRICEPS,
            body_region=BodyRegion.LOWER_BODY,
        ),
        _exercise(
            db,
            "service-hinge",
            MovementPattern.HIP_HINGE,
            MuscleGroup.HAMSTRINGS,
            body_region=BodyRegion.LOWER_BODY,
        ),
        _exercise(
            db,
            "service-plank",
            MovementPattern.CORE_ANTI_EXTENSION,
            MuscleGroup.ABS,
            body_region=BodyRegion.CORE,
            exercise_type=ExerciseType.CORE,
        ),
    ]


def _service(
    db: Session,
    *,
    provider: FakeWorkoutPlanModelProvider | None = None,
    cooldown_seconds: int = 0,
    body_analysis_resolver: BodyAnalysisInfluenceResolver | None = None,
) -> WorkoutGenerationService:
    providers = (
        (ModelProviderCandidate(model_id="legacy-model", provider=provider),)
        if provider is not None
        else ()
    )
    return WorkoutGenerationService(
        db,
        providers=providers,
        settings=WorkoutGenerationSettings(
            provider_name="fitsho_domain",
            model_id="program_engine_v1",
            prompt_version="none",
            generation_policy_version="resistance_training_v1",
            catalog_programming_version="v1",
            max_repair_attempts=0,
            cooldown_seconds=cooldown_seconds,
            max_candidates=5000,
            max_request_bytes=262144,
            warmup_minutes=5,
        ),
        body_analysis_resolver=body_analysis_resolver,
    )


class _InfluenceResolver:
    def __init__(self, influence: BodyAnalysisInfluence | None) -> None:
        self.influence = influence

    def resolve(self, _user_id):
        return self.influence


def _body_influence(*, result_version_id=None, source="ai_provisional", confidence=0.88):
    return BodyAnalysisInfluence.model_validate(
        {
            "analysis_id": "2cfda8dc-cb60-4adb-9105-1b367ff27b88",
            "result_version_id": result_version_id or "0a537064-afd4-40cc-8534-b86269037c9b",
            "analysis_revision": 1,
            "schema_version": "1.0",
            "source": source,
            "overall_confidence": 0.9,
            "priorities": [
                {
                    "muscle": "chest",
                    "classification": "mild_lag",
                    "confidence": confidence,
                    "severity": 0.5,
                    "emphasis": ["chest"],
                }
            ],
        }
    )


def test_generation_persists_valid_snapshot_then_reuses_signature(db: Session) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)
    service = _service(db)

    first = asyncio.run(service.generate(user.id))
    second = asyncio.run(service.generate(user.id))

    assert not first.reused
    assert second.reused
    assert second.plan.id == first.plan.id
    assert first.plan.status is WorkoutPlanStatus.ACTIVE
    assert first.plan.engine_version == "program_engine_v1"
    assert first.plan.ruleset_version == "resistance_training_v2"
    assert first.plan.validation_report["errors"] == []
    assert first.plan.exercise_catalog_snapshot["hash"] == first.plan.candidate_set_hash
    assert first.plan.generation_records[0].status is WorkoutGenerationStatus.SUCCEEDED
    assert first.plan.days[0].title_en == "Day 1: Chest + Back + Quadriceps + Hamstrings + Abs"
    assert first.plan.days[0].title_fa == "روز 1: سینه + زیربغل + چهارسر + پشت پا + شکم"


def test_generation_never_calls_legacy_model_provider(db: Session) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)
    provider = FakeWorkoutPlanModelProvider([])

    result = asyncio.run(_service(db, provider=provider).generate(user.id))

    assert result.plan.status is WorkoutPlanStatus.ACTIVE
    assert provider.calls == []
    assert result.plan.generation_method == "deterministic_domain"


def test_validation_failure_is_recorded_before_any_plan_is_persisted(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)
    monkeypatch.setattr(
        "app.workouts.service.generate_program",
        lambda *_args, **_kwargs: ProgramGenerationResult(
            program=None,
            error_code=GenerationErrorCode.PROGRAM_VALIDATION_FAILED,
            errors=("TEST_VALIDATION_ERROR",),
        ),
    )

    with pytest.raises(WorkoutGenerationFailedError):
        asyncio.run(_service(db).generate(user.id))

    assert db.query(WorkoutPlan).filter_by(user_id=user.id).count() == 0
    generation = db.query(WorkoutPlanGeneration).filter_by(user_id=user.id).one()
    assert generation.status is WorkoutGenerationStatus.FAILED
    assert generation.error_code == GenerationErrorCode.PROGRAM_VALIDATION_FAILED.value
    assert generation.validation_diagnostics == [
        {
            "model_id": "program_engine_v1",
            "phase": "initial",
            "problems": [
                {
                    "code": "TEST_VALIDATION_ERROR",
                    "message": "Deterministic program validation rejected this generation.",
                }
            ],
        }
    ]


def test_safety_red_flag_returns_professional_review_without_plan(db: Session) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)

    with pytest.raises(ProgramGenerationRejectedError) as error:
        asyncio.run(
            _service(db).generate(
                user.id,
                ProgramGenerationOverrides(current_pain_or_red_flags=(RedFlag.CHEST_PAIN,)),
            )
        )

    assert error.value.error_code == "PROGRAM_REJECTED_SAFETY_STATUS"
    assert db.query(WorkoutPlan).filter_by(user_id=user.id).count() == 0


def test_missing_safe_pattern_does_not_persist_partial_plan(db: Session) -> None:
    user = _user_with_profile(db)
    exercises = _seed_candidates(db)
    exercises[1].needs_review = True
    db.flush()

    with pytest.raises(NoEligibleExercisesError) as error:
        asyncio.run(_service(db).generate(user.id))

    assert error.value.error_code == "NO_SAFE_EXERCISE_FOR_PATTERN"
    assert db.query(WorkoutPlan).filter_by(user_id=user.id).count() == 0


def test_historical_response_uses_saved_exercise_snapshot_after_catalog_edit(
    db: Session,
) -> None:
    user = _user_with_profile(db)
    exercises = _seed_candidates(db)
    result = asyncio.run(_service(db).generate(user.id))
    saved_name = result.plan.days[0].exercises[0].exercise_snapshot["display_snapshot"]["name_en"]
    exercises[0].name_en = "catalog name changed later"
    db.commit()
    stored = get_plan_for_user(db, plan_id=result.plan.id, user_id=user.id)
    assert stored is not None

    response = to_plan_response(stored)

    assert response.days[0].exercises[0].exercise.name_en == saved_name


def test_request_time_seed_and_priority_are_persisted(db: Session) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)

    result = asyncio.run(
        _service(db).generate(
            user.id,
            ProgramGenerationOverrides(
                seed_optional=7,
                priority_muscles=frozenset({MuscleGroup.BACK}),
            ),
        )
    )

    assert result.plan.seed == 7
    assert result.plan.days[0].exercises[0].exercise_snapshot["primary_muscle"] == "back"
    assert "PRIORITY_MUSCLE_PLACED_FIRST" in result.plan.days[0].exercises[0].reason_codes


def test_failed_replacement_preserves_previous_active_plan(db: Session) -> None:
    user = _user_with_profile(db)
    exercises = _seed_candidates(db)
    initial = asyncio.run(_service(db).generate(user.id))
    profile = db.get(UserProfile, user.id)
    assert profile is not None
    profile.fitness_goal = FitnessGoal.IMPROVE_FITNESS
    exercises[1].needs_review = True
    db.commit()

    with pytest.raises(NoEligibleExercisesError):
        asyncio.run(_service(db).generate(user.id))

    assert db.get(WorkoutPlan, initial.plan.id).status is WorkoutPlanStatus.ACTIVE  # type: ignore[union-attr]


def test_generation_in_progress_rejects_second_request(db: Session) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)
    create_generation(
        db,
        user_id=user.id,
        provider="fitsho_domain",
        model_id="program_engine_v1",
        candidate_count=3,
    )
    db.commit()

    with pytest.raises(GenerationInProgressError):
        asyncio.run(_service(db).generate(user.id))

    assert db.query(WorkoutPlan).filter_by(user_id=user.id).count() == 0


def test_expired_plan_is_replaced_with_structured_difference(db: Session) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)
    first = asyncio.run(_service(db).generate(user.id))
    first.plan.activated_at = datetime.now(UTC) - timedelta(days=29)
    db.commit()

    replacement = asyncio.run(_service(db).generate(user.id))

    assert not replacement.reused
    assert replacement.plan.previous_program_id == first.plan.id
    assert replacement.plan.difference_summary["previous_program_id"] == str(first.plan.id)
    assert db.get(WorkoutPlan, first.plan.id).status is WorkoutPlanStatus.SUPERSEDED  # type: ignore[union-attr]


def test_active_plan_is_stale_when_profile_changes(db: Session) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)
    asyncio.run(_service(db).generate(user.id))
    profile = db.get(UserProfile, user.id)
    assert profile is not None
    profile.fitness_goal = FitnessGoal.IMPROVE_FITNESS
    db.commit()

    active = _service(db).get_active(user.id)

    assert active is not None
    assert active.is_stale


def test_generation_cooldown_prevents_another_generation(db: Session) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)
    asyncio.run(_service(db, cooldown_seconds=300).generate(user.id))
    profile = db.get(UserProfile, user.id)
    assert profile is not None
    profile.fitness_goal = FitnessGoal.IMPROVE_FITNESS
    db.commit()

    with pytest.raises(GenerationCooldownError) as error:
        asyncio.run(_service(db, cooldown_seconds=300).generate(user.id))

    assert 1 <= error.value.retry_after_seconds <= 300


def test_plan_persists_provisional_body_analysis_provenance(db: Session) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)
    resolver = _InfluenceResolver(_body_influence())

    result = asyncio.run(_service(db, body_analysis_resolver=resolver).generate(user.id))

    assert result.plan.body_analysis_provenance["source"] == "ai_provisional"
    assert result.plan.body_analysis_provenance["provisional"] is True
    assert any(
        item["stage"] == "body_analysis_influence"
        for item in result.plan.decision_trace
    )


def test_specialist_correction_changes_signature_and_marks_active_plan_stale(
    db: Session,
) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)
    resolver = _InfluenceResolver(_body_influence())
    service = _service(db, body_analysis_resolver=resolver)
    first = asyncio.run(service.generate(user.id))

    resolver.influence = _body_influence(
        result_version_id="2e9dd8b5-a70c-493e-b7b0-9832f9999c87",
        source="fully_reviewed",
    )

    active = service.get_active(user.id)
    replacement = asyncio.run(service.generate(user.id))

    assert active is not None and active.is_stale
    assert replacement.plan.id != first.plan.id
    assert replacement.plan.body_analysis_provenance["source"] == "fully_reviewed"


def test_low_confidence_analysis_reuses_same_plan_signature(db: Session) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)
    resolver = _InfluenceResolver(None)
    service = _service(db, body_analysis_resolver=resolver)
    first = asyncio.run(service.generate(user.id))

    resolver.influence = _body_influence(confidence=0.4)
    second = asyncio.run(service.generate(user.id))

    assert second.reused
    assert second.plan.id == first.plan.id
    assert second.plan.body_analysis_provenance == {}


def test_failed_body_analysis_does_not_block_normal_plan_generation(db: Session) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)
    photo_session = BodyPhotoSession(
        user_id=user.id,
        purpose=BodyPhotoPurpose.PROGRESS_CHECK,
        state=BodyPhotoSessionState.FAILED,
    )
    db.add(photo_session)
    db.flush()
    db.add(
        BodyAnalysis(
            session_id=photo_session.id,
            revision=1,
            provider="openrouter",
            model_id="vision",
            prompt_version="body-v1",
            schema_version="1.0",
            status=BodyAnalysisStatus.FAILED,
            error_code="provider_unavailable",
            error_message="safe message",
        )
    )
    db.commit()

    result = asyncio.run(_service(db).generate(user.id))

    assert result.plan.status is WorkoutPlanStatus.ACTIVE
    assert result.plan.body_analysis_provenance == {}
