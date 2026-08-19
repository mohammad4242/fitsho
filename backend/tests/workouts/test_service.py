import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.ai.schemas import ProviderErrorCode, WorkoutProviderError
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
    MediaPresentation,
    MediaType,
    MovementPattern,
    MuscleGroup,
)
from app.exercises.models import (
    Exercise,
    ExerciseEquipment,
    ExerciseMediaAsset,
    ExerciseSecondaryMuscle,
)
from app.exercises.taxonomy import FOCUSES_BY_MUSCLE
from app.profile.enums import ExperienceLevel, FitnessGoal, HomeTrainingSetup, Sex, TrainingLocation
from app.profile.models import BodyMeasurement, UserProfile
from app.profile.service import get_profile
from app.workout_cycles.enums import (
    WorkoutCycleStatus,
    WorkoutCycleWeeklyCheckInDifficulty,
    WorkoutCycleWeeklyCheckInRecovery,
)
from app.workout_cycles.models import WorkoutCycleFeedback, WorkoutCycleWeeklyCheckIn
from app.workout_cycles.schemas import CompletionFeedbackInput
from app.workout_cycles.service import complete_cycle, start_cycle
from app.workout_reviews.enums import WorkoutReviewStatus
from app.workout_reviews.models import WorkoutPlanReview
from app.workouts.ai_coach import AiCoachProgramCandidate
from app.workouts.ai_coach_provider import AiCoachRecommendation, OpenRouterAiCoachProvider
from app.workouts.body_analysis_resolver import BodyAnalysisInfluenceResolver
from app.workouts.enums import WorkoutGenerationStatus, WorkoutPlanStatus
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanGeneration
from app.workouts.program_engine.enums import (
    BodyPosition,
    GenerationErrorCode,
    Goal,
    ImpactLimit,
    Laterality,
    LoadLimit,
    RedFlag,
    SkillDemand,
    StabilityDemand,
)
from app.workouts.program_engine.schemas import (
    BodyAnalysisInfluence,
    ProgramGenerationResult,
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
)
from app.workouts.repository import create_generation, get_plan_for_user
from app.workouts.router import to_plan_response
from app.workouts.schemas import ProgramGenerationOverrides
from app.workouts.service import (
    GenerationCooldownError,
    GenerationInProgressError,
    ProgramGenerationRejectedError,
    WorkoutConstructionUnsatisfiedError,
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


def test_program_request_uses_persisted_profile_preferences(db: Session) -> None:
    user = _user_with_profile(db)
    profile = get_profile(db, user.id).profile
    profile.preferred_weekdays = [0, 3]
    profile.priority_muscles = [MuscleGroup.BACK.value]
    db.flush()
    service = _service(db)

    request = service._to_program_request(get_profile(db, user.id), None)

    assert request.preferred_weekdays == (0, 3)
    assert request.priority_muscles == frozenset({MuscleGroup.BACK})


def test_current_generation_overrides_take_precedence_over_profile_preferences(
    db: Session,
) -> None:
    user = _user_with_profile(db)
    profile = get_profile(db, user.id).profile
    profile.preferred_weekdays = [0, 3]
    profile.priority_muscles = [MuscleGroup.BACK.value]
    db.flush()
    service = _service(db)
    overrides = ProgramGenerationOverrides(
        preferred_weekdays=(1, 4),
        priority_muscles=frozenset({MuscleGroup.CHEST}),
    )

    request = service._to_program_request(get_profile(db, user.id), overrides)

    assert request.preferred_weekdays == (1, 4)
    assert request.priority_muscles == frozenset({MuscleGroup.CHEST})


def test_neutral_generation_overrides_do_not_erase_profile_preferences(db: Session) -> None:
    user = _user_with_profile(db)
    profile = get_profile(db, user.id).profile
    profile.preferred_weekdays = [0, 3]
    profile.priority_muscles = [MuscleGroup.BACK.value]
    db.flush()
    service = _service(db)

    request = service._to_program_request(get_profile(db, user.id), ProgramGenerationOverrides())

    assert request.preferred_weekdays == (0, 3)
    assert request.priority_muscles == frozenset({MuscleGroup.BACK})


def test_domain_candidate_uses_persisted_programming_metadata(db: Session) -> None:
    exercise = _exercise(
        db,
        "persisted-programming-metadata",
        MovementPattern.SQUAT,
        MuscleGroup.QUADRICEPS,
    )
    exercise.body_position = BodyPosition.SEATED
    exercise.stability_demand = StabilityDemand.LOW
    exercise.skill_demand = SkillDemand.LOW
    exercise.impact_level = ImpactLimit.HIGH
    exercise.axial_loading_level = LoadLimit.NONE
    exercise.fatigue_cost = 5
    exercise.setup_cost = 4
    exercise.laterality = Laterality.NOT_APPLICABLE
    exercise.substitution_group = "curated-squat"
    exercise.range_of_motion_profile = ["shortened", "supported"]
    db.flush()

    candidate = WorkoutGenerationService._domain_candidate(exercise)

    assert candidate.body_position is BodyPosition.SEATED
    assert candidate.stability_demand is StabilityDemand.LOW
    assert candidate.skill_demand is SkillDemand.LOW
    assert candidate.impact_level is ImpactLimit.HIGH
    assert candidate.axial_loading_level is LoadLimit.NONE
    assert candidate.fatigue_cost == 5
    assert candidate.setup_cost == 4
    assert candidate.laterality is Laterality.NOT_APPLICABLE
    assert candidate.substitution_group == "curated-squat"
    assert candidate.range_of_motion_profile == frozenset({"shortened", "supported"})


def test_domain_candidate_uses_legacy_fallback_only_for_missing_metadata(db: Session) -> None:
    exercise = _exercise(
        db,
        "legacy-programming-metadata",
        MovementPattern.SQUAT,
        MuscleGroup.QUADRICEPS,
    )
    exercise.difficulty = Difficulty.ADVANCED
    db.flush()

    candidate = WorkoutGenerationService._domain_candidate(exercise)

    assert candidate.body_position is BodyPosition.STANDING
    assert candidate.stability_demand is StabilityDemand.MODERATE
    assert candidate.skill_demand is SkillDemand.HIGH
    assert candidate.impact_level is ImpactLimit.LOW
    assert candidate.axial_loading_level is LoadLimit.LOW
    assert candidate.fatigue_cost == 3
    assert candidate.setup_cost == 1
    assert candidate.laterality is Laterality.BILATERAL
    assert candidate.substitution_group == MovementPattern.SQUAT.value
    assert candidate.range_of_motion_profile == frozenset()


def test_catalog_snapshot_keeps_programming_metadata_and_stable_collections(
    db: Session,
) -> None:
    exercise = _exercise(
        db,
        "snapshot-programming-metadata",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
    )
    exercise.body_position = BodyPosition.SUPPORTED
    exercise.range_of_motion_profile = ["z_profile", "a_profile"]
    db.flush()

    candidate = WorkoutGenerationService._domain_candidate(exercise)
    snapshot = WorkoutGenerationService._candidate_snapshot(candidate)

    assert snapshot["body_position"] == "supported"
    assert snapshot["range_of_motion_profile"] == ["a_profile", "z_profile"]


def _exercise(
    db: Session,
    slug: str,
    pattern: MovementPattern,
    muscle: MuscleGroup,
    *,
    body_region: BodyRegion = BodyRegion.UPPER_BODY,
    exercise_type: ExerciseType = ExerciseType.COMPOUND,
    secondary_muscles: tuple[MuscleGroup, ...] = (),
) -> Exercise:
    item = Exercise(
        slug=slug,
        name_en=slug,
        name_fa=slug,
        body_region=body_region,
        primary_muscle=muscle,
        muscle_focus=next(iter(FOCUSES_BY_MUSCLE[muscle]), None),
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
        secondary_muscles=[ExerciseSecondaryMuscle(muscle=value) for value in secondary_muscles],
    )
    db.add(item)
    db.flush()
    return item


def _seed_candidates(db: Session) -> list[Exercise]:
    return [
        _exercise(
            db,
            "service-push",
            MovementPattern.HORIZONTAL_PUSH,
            MuscleGroup.CHEST,
            secondary_muscles=(MuscleGroup.SHOULDERS,),
        ),
        _exercise(db, "service-pull", MovementPattern.HORIZONTAL_PULL, MuscleGroup.BACK),
        _exercise(
            db,
            "service-squat",
            MovementPattern.SQUAT,
            MuscleGroup.QUADRICEPS,
            body_region=BodyRegion.LOWER_BODY,
            secondary_muscles=(MuscleGroup.GLUTES,),
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
        _exercise(
            db,
            "service-calf-raise",
            MovementPattern.CALF_RAISE,
            MuscleGroup.CALVES,
            body_region=BodyRegion.LOWER_BODY,
            exercise_type=ExerciseType.ISOLATION,
        ),
    ]


def _ai_template(slug: str, exercise_ids: tuple[object, ...]) -> TemplateReference:
    return TemplateReference(
        slug=slug,
        days_per_week=2,
        training_level="beginner",
        fitness_goal="build_muscle",
        focus_tags=("general",),
        intensity_methods=("standard",),
        days=tuple(
            TemplateReferenceDay(
                day_number=index,
                title=f"Day {index}",
                focus=(MuscleGroup.CHEST,),
                slots=(
                    TemplateReferenceSlot(
                        exercise_id=exercise_id,
                        exercise_slug_hint="service-push",
                        target_muscles=(MuscleGroup.CHEST,),
                        movement_pattern=MovementPattern.HORIZONTAL_PUSH,
                        intensity_method="standard",
                        adaptation_priority="core",
                        superset_group=None,
                        sets=3,
                        rep_min=8,
                        rep_max=12,
                        target_rir=2,
                        rest_seconds=90,
                    ),
                ),
            )
            for index, exercise_id in enumerate(exercise_ids, start=1)
        ),
    )


class _FailingAiCoachProvider(OpenRouterAiCoachProvider):
    def __init__(self, failure: BaseException | object) -> None:
        self.calls = 0
        self._failure = failure

    async def recommend(self, request: object) -> object:
        self.calls += 1
        if isinstance(self._failure, BaseException):
            raise self._failure
        return self._failure


def _service(
    db: Session,
    *,
    cooldown_seconds: int = 0,
    body_analysis_resolver: BodyAnalysisInfluenceResolver | None = None,
    ai_coach_provider: OpenRouterAiCoachProvider | None = None,
    generation_method: str = "deterministic_domain",
    deterministic_fallback_enabled: bool = True,
) -> WorkoutGenerationService:
    return WorkoutGenerationService(
        db,
        ai_coach_provider=ai_coach_provider,
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
            deterministic_fallback_enabled=deterministic_fallback_enabled,
            generation_method=generation_method,
        ),
        body_analysis_resolver=body_analysis_resolver,
    )


def _persist_active_plan(
    db: Session,
    user: User,
    *,
    activated_at: datetime | None = None,
) -> WorkoutPlan:
    plan = WorkoutPlan(
        user_id=user.id,
        status=WorkoutPlanStatus.ACTIVE,
        generation_signature="z" * 64,
        profile_snapshot={"plan_duration_weeks": 4},
        provider="fitsho_domain",
        model_id="program_engine_v1",
        prompt_version="none",
        generation_policy_version="resistance_training_v2",
        candidate_set_hash="y" * 64,
        generation_method="deterministic_domain",
        activated_at=activated_at or datetime.now(UTC),
    )
    db.add(plan)
    db.commit()
    return plan


def test_program_request_uses_stored_training_age_over_experience_fallback(
    db: Session,
) -> None:
    user = _user_with_profile(db)
    profile = db.get(UserProfile, user.id)
    assert profile is not None
    profile.experience_level = ExperienceLevel.ADVANCED
    profile.training_age_months = 7
    db.flush()

    request = _service(db)._to_program_request(get_profile(db, user.id), None)

    assert request.training_age_months == 7


def test_program_request_uses_legacy_training_age_fallback_when_missing(
    db: Session,
) -> None:
    user = _user_with_profile(db)
    profile = db.get(UserProfile, user.id)
    assert profile is not None
    profile.experience_level = ExperienceLevel.INTERMEDIATE
    profile.training_age_months = None
    db.flush()

    request = _service(db)._to_program_request(get_profile(db, user.id), None)

    assert request.training_age_months == 12


def test_next_generation_reads_confirmed_end_cycle_profile_changes(db: Session) -> None:
    user = _user_with_profile(db)
    plan = _persist_active_plan(db, user)
    cycle = start_cycle(db, user_id=user.id, workout_plan_id=plan.id)

    complete_cycle(
        db,
        cycle_id=cycle.id,
        user_id=user.id,
        feedback=CompletionFeedbackInput(
            goal_changed=True,
            next_goal=Goal.FAT_LOSS,
            schedule_changed=True,
            next_training_days=3,
            next_session_duration_minutes=75,
            next_preferred_weekdays=[1, 3, 5],
        ),
    )

    request = _service(db)._to_program_request(get_profile(db, user.id), None)

    assert request.primary_goal == FitnessGoal.FAT_LOSS.value
    assert request.available_training_days == 3
    assert request.session_duration_minutes == 75
    assert request.preferred_weekdays == (1, 3, 5)


def test_previous_cycle_volume_history_uses_plan_metrics_and_confirmed_adherence(
    db: Session,
) -> None:
    user = _user_with_profile(db)
    plan = _persist_active_plan(db, user)
    plan.aggregate_metrics = {
        "weekly_direct_sets_by_muscle": {"chest": 8},
        "weekly_effective_sets_by_muscle": {"chest": 10.0, "triceps": 4.0},
    }
    plan.days.extend(
        [
            WorkoutDay(
                day_number=1,
                title_en="Day 1",
                title_fa="روز ۱",
                estimated_duration_minutes=45,
            ),
            WorkoutDay(
                day_number=2,
                title_en="Day 2",
                title_fa="روز ۲",
                estimated_duration_minutes=45,
            ),
        ]
    )
    db.flush()
    cycle = start_cycle(db, user_id=user.id, workout_plan_id=plan.id)
    cycle.status = WorkoutCycleStatus.COMPLETED
    cycle.completed_at = datetime.now(UTC)
    cycle.completion_feedback = WorkoutCycleFeedback(
        adherence_percent=80,
        measurements={},
    )
    db.flush()

    history = _service(db)._previous_volume_history(user.id)

    assert history is not None
    assert history.completed_session_ratio == 0.8
    assert history.previous_volume_source == "prescribed_plan"
    assert history.previous_weekly_direct_sets_by_muscle[MuscleGroup.CHEST] == 8.0
    assert history.previous_weekly_effective_sets_by_muscle[MuscleGroup.CHEST] == 10.0
    assert "HISTORY_FROM_COMPLETED_PLAN" in history.previous_volume_reason_codes


def test_previous_cycle_volume_history_scales_from_weekly_check_ins(
    db: Session,
) -> None:
    user = _user_with_profile(db)
    plan = _persist_active_plan(db, user)
    plan.aggregate_metrics = {
        "weekly_direct_sets_by_muscle": {"chest": 8},
        "weekly_effective_sets_by_muscle": {"chest": 10.0},
    }
    plan.days.extend(
        [
            WorkoutDay(
                day_number=1,
                title_en="Day 1",
                title_fa="روز ۱",
                estimated_duration_minutes=45,
            ),
            WorkoutDay(
                day_number=2,
                title_en="Day 2",
                title_fa="روز ۲",
                estimated_duration_minutes=45,
            ),
        ]
    )
    db.flush()
    cycle = start_cycle(db, user_id=user.id, workout_plan_id=plan.id)
    cycle.status = WorkoutCycleStatus.COMPLETED
    cycle.completed_at = datetime.now(UTC)
    db.add_all(
        [
            WorkoutCycleWeeklyCheckIn(
                user_id=user.id,
                cycle_id=cycle.id,
                week_number=1,
                sessions_completed=1,
                perceived_difficulty=WorkoutCycleWeeklyCheckInDifficulty.APPROPRIATE,
                recovery_rating=WorkoutCycleWeeklyCheckInRecovery.GOOD,
                has_pain_or_limitation=False,
            ),
            WorkoutCycleWeeklyCheckIn(
                user_id=user.id,
                cycle_id=cycle.id,
                week_number=2,
                sessions_completed=0,
                perceived_difficulty=WorkoutCycleWeeklyCheckInDifficulty.HARD,
                recovery_rating=WorkoutCycleWeeklyCheckInRecovery.AVERAGE,
                has_pain_or_limitation=False,
            ),
        ]
    )
    db.flush()

    history = _service(db)._previous_volume_history(user.id)

    assert history is not None
    assert history.completed_session_ratio == 0.25
    assert history.previous_weekly_effective_sets_by_muscle[MuscleGroup.CHEST] == 10.0


def test_catalog_uses_profile_gender_media_and_falls_back_to_other_gender(
    db: Session,
) -> None:
    _user_with_profile(db)
    exercise = _exercise(
        db,
        "gendered-service-push",
        MovementPattern.HORIZONTAL_PUSH,
        MuscleGroup.CHEST,
    )
    exercise.media_assets.extend(
        [
            ExerciseMediaAsset(
                presentation=MediaPresentation.MALE,
                role="video",
                sort_order=0,
                media_path="/media/male.mp4",
                media_type=MediaType.VIDEO,
            ),
            ExerciseMediaAsset(
                presentation=MediaPresentation.FEMALE,
                role="video",
                sort_order=0,
                media_path="/media/female.mp4",
                media_type=MediaType.VIDEO,
            ),
        ]
    )
    db.commit()
    service = _service(db)

    male_candidate = {item.id: item for item in service._load_catalog(Sex.MALE)}[exercise.id]
    assert male_candidate.display_snapshot["media_path"] == "/media/male.mp4"

    male_asset = next(
        asset for asset in exercise.media_assets if asset.presentation is MediaPresentation.MALE
    )
    db.delete(male_asset)
    db.commit()

    fallback_candidate = {item.id: item for item in service._load_catalog(Sex.MALE)}[exercise.id]
    assert fallback_candidate.display_snapshot["media_path"] == "/media/female.mp4"


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


def test_generation_persists_valid_snapshot_for_pending_review(db: Session) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)
    service = _service(db)

    result = asyncio.run(service.generate(user.id))
    review = db.query(WorkoutPlanReview).filter_by(source_plan_id=result.plan.id).one()

    assert not result.reused
    assert result.plan.status is WorkoutPlanStatus.PENDING_REVIEW
    assert result.plan.activated_at is None
    assert result.plan.engine_version == "program_engine_v1"
    assert result.plan.ruleset_version == "resistance_training_v2"
    assert result.plan.validation_report["errors"] == []
    assert result.plan.exercise_catalog_snapshot["hash"] == result.plan.candidate_set_hash
    assert result.plan.generation_records[0].status is WorkoutGenerationStatus.SUCCEEDED
    assert review.status is WorkoutReviewStatus.PENDING
    assert result.plan.days[0].title_en == (
        "Day 1: Chest + Back + Quadriceps + Hamstrings + Calves"
    )
    assert result.plan.days[0].title_fa == "روز 1: سینه + زیربغل + چهارسر + پشت پا + ساق"


def test_generation_keeps_existing_active_plan_when_new_plan_is_pending_review(
    db: Session,
) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)
    active_plan = _persist_active_plan(db, user)

    result = asyncio.run(_service(db).generate(user.id))

    assert result.plan.status is WorkoutPlanStatus.PENDING_REVIEW
    assert db.get(WorkoutPlan, active_plan.id).status is WorkoutPlanStatus.ACTIVE


def test_generation_uses_the_deterministic_domain_engine(db: Session) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)

    result = asyncio.run(_service(db).generate(user.id))

    assert result.plan.status is WorkoutPlanStatus.PENDING_REVIEW
    assert result.plan.generation_method == "deterministic_domain"
    assert result.plan.generation_method == "deterministic_domain"


def test_internal_generation_never_calls_ai_provider(db: Session) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)
    provider = _FailingAiCoachProvider(TimeoutError("must not be called"))

    result = asyncio.run(
        _service(
            db,
            ai_coach_provider=provider,
            generation_method="deterministic_domain",
        ).generate(user.id)
    )

    assert result.plan.generation_method == "deterministic_domain"
    assert provider.calls == 0


def test_ai_provider_unavailable_falls_back_to_one_deterministic_reviewable_plan(
    db: Session,
) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)

    result = asyncio.run(
        _service(
            db,
            generation_method="ai",
            deterministic_fallback_enabled=True,
        ).generate(user.id)
    )

    assert result.plan.status is WorkoutPlanStatus.PENDING_REVIEW
    assert result.plan.generation_method == "deterministic_domain"
    assert "AI_REASONING_FALLBACK" in result.plan.warnings
    assert result.plan.decision_trace[-1] == {
        "stage": "ai_reasoning",
        "status": "fallback",
        "reason_code": "AI_PROVIDER_UNAVAILABLE",
        "source": "deterministic_domain",
        "ai_output_persisted": False,
    }
    assert db.query(WorkoutPlan).filter_by(user_id=user.id).count() == 1
    assert db.query(WorkoutPlanReview).filter_by(user_id=user.id).count() == 1
    generation = db.query(WorkoutPlanGeneration).filter_by(user_id=user.id).one()
    assert generation.status is WorkoutGenerationStatus.SUCCEEDED
    assert generation.provider == "fitsho_domain"
    assert generation.workout_plan_id == result.plan.id


@pytest.mark.parametrize(
    ("failure", "expected_reason_code"),
    [
        (
            WorkoutProviderError(ProviderErrorCode.TIMEOUT, "AI timed out"),
            "TIMEOUT",
        ),
        (
            WorkoutProviderError(ProviderErrorCode.PROVIDER_UNAVAILABLE, "AI unavailable"),
            "PROVIDER_UNAVAILABLE",
        ),
        (
            WorkoutProviderError(ProviderErrorCode.INVALID_OUTPUT, "AI schema was invalid"),
            "INVALID_OUTPUT",
        ),
        (object(), "AI_OUTPUT_INVALID"),
        (
            AiCoachRecommendation(
                selected_candidate_id="not-supplied",
                program_explanation_fa="نامعتبر",
                day_explanations=(),
                model_id="test-model",
                provider_request_id=None,
                input_tokens=None,
                output_tokens=None,
            ),
            "AI_OUTPUT_INVALID",
        ),
    ],
)
def test_ai_failure_keeps_deterministic_plan_and_does_not_duplicate_records(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    failure: BaseException | object,
    expected_reason_code: str,
) -> None:
    user = _user_with_profile(db)
    exercises = _seed_candidates(db)
    templates = (
        AiCoachProgramCandidate(
            template=_ai_template("candidate-a", (exercises[0].id, exercises[1].id)),
            score=100,
        ),
        AiCoachProgramCandidate(
            template=_ai_template("candidate-b", (exercises[1].id, exercises[0].id)),
            score=90,
        ),
    )
    monkeypatch.setattr(
        "app.workouts.service.select_ai_coach_candidates",
        lambda **_kwargs: templates,
    )
    provider = _FailingAiCoachProvider(failure)

    result = asyncio.run(
        _service(
            db,
            ai_coach_provider=provider,
            generation_method="ai",
            deterministic_fallback_enabled=True,
        ).generate(user.id)
    )

    assert provider.calls == 1
    assert result.plan.generation_method == "deterministic_domain"
    assert result.plan.status is WorkoutPlanStatus.PENDING_REVIEW
    assert result.plan.decision_trace[-1]["reason_code"] == expected_reason_code
    assert result.plan.decision_trace[-1]["ai_output_persisted"] is False
    assert db.query(WorkoutPlan).filter_by(user_id=user.id).count() == 1
    assert db.query(WorkoutPlanReview).filter_by(user_id=user.id).count() == 1
    assert db.query(WorkoutPlanGeneration).filter_by(user_id=user.id).count() == 1


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

    with pytest.raises(WorkoutConstructionUnsatisfiedError) as error:
        asyncio.run(_service(db).generate(user.id))

    assert error.value.error_code == "UNSATISFIED_CONSTRAINT"
    assert db.query(WorkoutPlan).filter_by(user_id=user.id).count() == 0
    generation = db.query(WorkoutPlanGeneration).filter_by(user_id=user.id).one()
    assert generation.safe_error_message == (
        "No safe workout layout satisfies all required session constraints."
    )
    assert generation.validation_diagnostics is not None
    assert {
        problem["message"]
        for diagnostic in generation.validation_diagnostics
        for problem in diagnostic["problems"]
    } == {"Safe program construction exhausted all ranked split alternatives."}


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
    active_plan = _persist_active_plan(db, user)
    initial = asyncio.run(_service(db).generate(user.id))
    profile = db.get(UserProfile, user.id)
    assert profile is not None
    profile.fitness_goal = FitnessGoal.IMPROVE_FITNESS
    exercises[1].needs_review = True
    db.commit()

    with pytest.raises(WorkoutConstructionUnsatisfiedError):
        asyncio.run(_service(db).generate(user.id))

    assert initial.plan.status is WorkoutPlanStatus.PENDING_REVIEW
    assert db.get(WorkoutPlan, active_plan.id).status is WorkoutPlanStatus.ACTIVE


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
    first = _persist_active_plan(
        db,
        user,
        activated_at=datetime.now(UTC) - timedelta(days=29),
    )

    replacement = asyncio.run(_service(db).generate(user.id))

    assert not replacement.reused
    assert replacement.plan.status is WorkoutPlanStatus.PENDING_REVIEW
    assert replacement.plan.previous_program_id == first.id
    assert replacement.plan.difference_summary["previous_program_id"] == str(first.id)
    assert db.get(WorkoutPlan, first.id).status is WorkoutPlanStatus.ACTIVE


def test_active_plan_is_stale_when_profile_changes(db: Session) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)
    _persist_active_plan(db, user)
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
    assert any(item["stage"] == "body_analysis_influence" for item in result.plan.decision_trace)


def test_specialist_correction_changes_signature_and_marks_active_plan_stale(
    db: Session,
) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)
    _persist_active_plan(db, user)
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
    assert replacement.plan.status is WorkoutPlanStatus.PENDING_REVIEW
    assert replacement.plan.body_analysis_provenance["source"] == "fully_reviewed"


def test_low_confidence_analysis_reuses_same_plan_signature(db: Session) -> None:
    user = _user_with_profile(db)
    _seed_candidates(db)
    resolver = _InfluenceResolver(None)
    service = _service(db, body_analysis_resolver=resolver)
    first = asyncio.run(service.generate(user.id))
    first.plan.status = WorkoutPlanStatus.ACTIVE
    first.plan.activated_at = datetime.now(UTC)
    db.commit()

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

    assert result.plan.status is WorkoutPlanStatus.PENDING_REVIEW
    assert result.plan.body_analysis_provenance == {}
