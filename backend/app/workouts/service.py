from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from time import perf_counter
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.provider import WorkoutPlanModelProvider
from app.ai.schemas import (
    WorkoutGenerationModelRequest,
    WorkoutGenerationModelResponse,
    WorkoutPlanModelOutput,
    WorkoutProviderError,
)
from app.profile.service import ProfileSnapshot, get_profile
from app.workouts.candidate_selector import WorkoutCandidateSelector
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanExercise, WorkoutPlanGeneration
from app.workouts.prompt_builder import build_workout_generation_model_request
from app.workouts.repository import (
    activate_plan,
    create_generation,
    fail_generation,
    get_active_plan,
)
from app.workouts.schemas import CandidateSet, GenerationSignatureContext, WorkoutGenerationProfile
from app.workouts.signature import build_generation_signature, normalize_physical_limitations
from app.workouts.time_budget import WorkoutGenerationPolicy
from app.workouts.validator import WorkoutPlanValidationError, WorkoutPlanValidator


@dataclass(frozen=True)
class WorkoutGenerationSettings:
    provider_name: str
    model_id: str
    prompt_version: str
    generation_policy_version: str
    catalog_programming_version: str
    max_repair_attempts: int


@dataclass(frozen=True)
class WorkoutPlanGenerationResult:
    plan: WorkoutPlan
    reused: bool


class GenerationInProgressError(Exception):
    pass


class NoEligibleExercisesError(Exception):
    pass


class WorkoutGenerationFailedError(Exception):
    pass


class WorkoutGenerationService:
    def __init__(
        self,
        db: Session,
        *,
        provider: WorkoutPlanModelProvider,
        settings: WorkoutGenerationSettings,
    ) -> None:
        self._db = db
        self._provider = provider
        self._settings = settings

    async def generate(self, user_id: UUID) -> WorkoutPlanGenerationResult:
        source_profile = get_profile(self._db, user_id)
        profile = self._to_generation_profile(source_profile)
        candidates = WorkoutCandidateSelector(self._db).select(profile)
        if not candidates.is_sufficient:
            raise NoEligibleExercisesError
        policy = WorkoutGenerationPolicy.for_session_duration(profile.session_duration_minutes)
        signature = build_generation_signature(
            GenerationSignatureContext(
                fitness_goal=profile.fitness_goal,
                experience_level=profile.experience_level,
                training_days_per_week=profile.training_days_per_week,
                training_location=profile.training_location,
                home_training_setup=profile.home_training_setup,
                session_duration_minutes=profile.session_duration_minutes,
                plan_duration_weeks=profile.plan_duration_weeks,
                training_cautions=profile.training_cautions,
                physical_limitations=profile.physical_limitations,
                current_weight_kg=profile.current_weight_kg,
                candidate_set_hash=candidates.candidate_set_hash,
                catalog_programming_version=self._settings.catalog_programming_version,
                model_id=self._settings.model_id,
                prompt_version=self._settings.prompt_version,
                generation_policy_version=self._settings.generation_policy_version,
            )
        )
        active_plan = get_active_plan(self._db, user_id)
        if active_plan is not None and active_plan.generation_signature == signature:
            return WorkoutPlanGenerationResult(plan=active_plan, reused=True)

        generation = self._start_generation(user_id, len(candidates.exercises))
        request = build_workout_generation_model_request(profile, candidates, policy)
        started_at = perf_counter()
        try:
            response = await self._generate_valid_response(
                request=request,
                candidates=candidates,
                policy=policy,
                required_day_count=profile.training_days_per_week,
            )
            refreshed_candidates = WorkoutCandidateSelector(self._db).select(profile)
            if refreshed_candidates.candidate_set_hash != candidates.candidate_set_hash:
                raise WorkoutGenerationFailedError
            plan = self._build_plan(
                user_id=user_id,
                signature=signature,
                profile_snapshot=self._profile_snapshot(request),
                candidate_set_hash=candidates.candidate_set_hash,
                response=response.plan,
            )
            generation.provider_request_id = response.provider_request_id
            generation.input_tokens = response.input_tokens
            generation.output_tokens = response.output_tokens
            generation.latency_ms = int((perf_counter() - started_at) * 1000)
            activate_plan(self._db, plan, generation)
            self._db.commit()
            return WorkoutPlanGenerationResult(plan=plan, reused=False)
        except WorkoutProviderError as error:
            self._mark_failure(generation, error.code.value, error.safe_message)
        except WorkoutPlanValidationError:
            self._mark_failure(
                generation,
                "semantic_validation_failed",
                "Workout generation returned an invalid plan. Please try again.",
            )
        except WorkoutGenerationFailedError:
            self._mark_failure(
                generation,
                "catalog_changed",
                "Workout exercises changed while the plan was being generated. Please try again.",
            )
        except SQLAlchemyError:
            self._db.rollback()
            self._mark_failure(
                generation,
                "persistence_failed",
                "Workout generation could not be saved. Please try again.",
            )
        raise WorkoutGenerationFailedError

    def _start_generation(self, user_id: UUID, candidate_count: int) -> WorkoutPlanGeneration:
        try:
            generation = create_generation(
                self._db,
                user_id=user_id,
                provider=self._settings.provider_name,
                model_id=self._settings.model_id,
                candidate_count=candidate_count,
            )
            self._db.commit()
        except IntegrityError as error:
            self._db.rollback()
            raise GenerationInProgressError from error
        return generation

    async def _generate_valid_response(
        self,
        *,
        request: WorkoutGenerationModelRequest,
        candidates: CandidateSet,
        policy: WorkoutGenerationPolicy,
        required_day_count: int,
    ) -> WorkoutGenerationModelResponse:

        validator = WorkoutPlanValidator(
            candidates=candidates,
            policy=policy,
            required_day_count=required_day_count,
        )
        response = await self._provider.generate_plan(request)
        try:
            validator.validate(response.plan)
            return response
        except WorkoutPlanValidationError as initial_error:
            if self._settings.max_repair_attempts < 1:
                raise
            repair_request = replace(
                request,
                input_payload={
                    **request.input_payload,
                    "repair": {
                        "instruction": (
                            "Return the complete plan again using the same allowed exercises."
                        ),
                        "validation_problems": [
                            problem.to_repair_payload() for problem in initial_error.problems
                        ],
                    },
                },
            )
            repaired = await self._provider.generate_plan(repair_request)
            validator.validate(repaired.plan)
            return repaired

    @staticmethod
    def _profile_snapshot(request: WorkoutGenerationModelRequest) -> dict[str, object]:
        profile = request.input_payload.get("profile")
        if not isinstance(profile, dict):
            raise ValueError("Workout profile payload is invalid")
        return dict(profile)

    def _build_plan(
        self,
        *,
        user_id: UUID,
        signature: str,
        profile_snapshot: dict[str, object],
        candidate_set_hash: str,
        response: WorkoutPlanModelOutput,
    ) -> WorkoutPlan:

        plan = WorkoutPlan(
            user_id=user_id,
            status=WorkoutPlanStatus.GENERATING,
            generation_signature=signature,
            profile_snapshot=profile_snapshot,
            provider=self._settings.provider_name,
            model_id=self._settings.model_id,
            prompt_version=self._settings.prompt_version,
            generation_policy_version=self._settings.generation_policy_version,
            candidate_set_hash=candidate_set_hash,
            generation_method="ai",
        )
        for output_day in response.days:
            day = WorkoutDay(
                day_number=output_day.day_number,
                title_en=output_day.title_en,
                title_fa=output_day.title_fa,
                estimated_duration_minutes=output_day.estimated_duration_minutes,
            )
            for order_index, output_exercise in enumerate(output_day.exercises, start=1):
                day.exercises.append(
                    WorkoutPlanExercise(
                        exercise_id=output_exercise.exercise_id,
                        order_index=order_index,
                        sets=output_exercise.sets,
                        reps_min=output_exercise.reps_min,
                        reps_max=output_exercise.reps_max,
                        rest_seconds=output_exercise.rest_seconds,
                        rir=output_exercise.rir,
                        estimated_minutes=output_exercise.estimated_minutes,
                        notes_en=output_exercise.notes_en,
                        notes_fa=output_exercise.notes_fa,
                    )
                )
            plan.days.append(day)
        return plan

    @staticmethod
    def _to_generation_profile(source: ProfileSnapshot) -> WorkoutGenerationProfile:

        profile = source.profile
        age = WorkoutGenerationService._age(profile.birth_date)
        cautions = tuple(
            sorted(
                (item.caution for item in profile.training_caution_items),
                key=lambda item: item.value,
            )
        )
        return WorkoutGenerationProfile(
            fitness_goal=profile.fitness_goal,
            experience_level=profile.experience_level,
            training_days_per_week=profile.training_days_per_week,
            training_location=profile.training_location,
            home_training_setup=profile.home_training_setup,
            session_duration_minutes=profile.session_duration_minutes,
            plan_duration_weeks=profile.plan_duration_weeks,
            training_cautions=cautions,
            physical_limitations=WorkoutGenerationService._sanitize_limitations(
                profile.physical_limitations
            ),
            current_weight_kg=source.measurement.weight_kg,
            age=age,
            sex=profile.sex,
            height_cm=profile.height_cm,
        )

    @staticmethod
    def _age(birth_date: date) -> int:
        today = date.today()
        return (
            today.year
            - birth_date.year
            - ((today.month, today.day) < (birth_date.month, birth_date.day))
        )

    @staticmethod
    def _sanitize_limitations(value: str | None) -> str | None:
        normalized = normalize_physical_limitations(value)
        return normalized[:500] if normalized is not None else None

    def _mark_failure(
        self,
        generation: WorkoutPlanGeneration,
        error_code: str,
        safe_message: str,
    ) -> None:
        try:
            if generation not in self._db:
                generation = self._db.get(WorkoutPlanGeneration, generation.id) or generation
            fail_generation(
                self._db,
                generation,
                error_code=error_code,
                safe_error_message=safe_message,
            )
            self._db.commit()
        except SQLAlchemyError:
            self._db.rollback()
