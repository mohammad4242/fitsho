from __future__ import annotations

import json
import logging
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from math import ceil
from time import perf_counter
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.routing import ModelProviderCandidate
from app.ai.schemas import (
    ProviderErrorCode,
    WorkoutGenerationModelRequest,
    WorkoutGenerationModelResponse,
    WorkoutPlanModelOutput,
    WorkoutProviderError,
)
from app.profile.service import ProfileSnapshot, get_profile
from app.workouts.candidate_selector import WorkoutCandidateSelector
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanExercise, WorkoutPlanGeneration
from app.workouts.normalizer import normalize_workout_plan
from app.workouts.prompt_builder import build_workout_generation_model_request
from app.workouts.repository import (
    activate_plan,
    create_generation,
    fail_generation,
    get_active_plan,
    get_latest_completed_generation_at,
)
from app.workouts.schemas import CandidateSet, GenerationSignatureContext, WorkoutGenerationProfile
from app.workouts.signature import build_generation_signature, normalize_physical_limitations
from app.workouts.time_budget import (
    ExerciseTiming,
    WorkoutGenerationPolicy,
    calculate_day_minutes,
    calculate_exercise_minutes,
)
from app.workouts.validator import WorkoutPlanValidationError, WorkoutPlanValidator

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkoutGenerationSettings:
    provider_name: str
    model_id: str
    prompt_version: str
    generation_policy_version: str
    catalog_programming_version: str
    max_repair_attempts: int
    cooldown_seconds: int
    max_candidates: int
    max_request_bytes: int
    warmup_minutes: int


@dataclass(frozen=True)
class WorkoutPlanGenerationResult:
    plan: WorkoutPlan
    reused: bool


@dataclass(frozen=True)
class ActiveWorkoutPlanResult:
    plan: WorkoutPlan
    is_stale: bool


@dataclass(frozen=True)
class ModelGenerationResponse:
    model_id: str
    response: WorkoutGenerationModelResponse


class GenerationInProgressError(Exception):
    pass


class GenerationCooldownError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds


class NoEligibleExercisesError(Exception):
    pass


class WorkoutGenerationFailedError(Exception):
    def __init__(self, provider_error_code: ProviderErrorCode | None = None) -> None:
        self.provider_error_code = provider_error_code


class GenerationInputsChangedError(Exception):
    pass


def _log_validation_failure(
    model_id: str,
    phase: str,
    error: WorkoutPlanValidationError,
) -> None:
    problems = [problem.to_repair_payload() for problem in error.problems]
    logger.warning(
        "workout_plan_validation_failed model_id=%s phase=%s problems=%s",
        model_id,
        phase,
        json.dumps(problems, ensure_ascii=False, separators=(",", ":")),
        extra={
            "workout_model_id": model_id,
            "validation_phase": phase,
            "validation_problems": problems,
        },
    )


def _validation_diagnostic(
    model_id: str,
    phase: str,
    error: WorkoutPlanValidationError,
) -> dict[str, object]:
    return {
        "model_id": model_id,
        "phase": phase,
        "problems": [problem.to_repair_payload() for problem in error.problems],
    }


class WorkoutGenerationService:
    def __init__(
        self,
        db: Session,
        *,
        providers: tuple[ModelProviderCandidate, ...],
        settings: WorkoutGenerationSettings,
    ) -> None:
        if not providers:
            raise ValueError("At least one workout model provider is required")
        self._db = db
        self._providers = providers
        self._settings = settings

    async def generate(self, user_id: UUID) -> WorkoutPlanGenerationResult:
        source_profile = get_profile(self._db, user_id)
        profile = self._to_generation_profile(source_profile)
        candidates = self._select_candidates(profile)
        if not candidates.is_sufficient:
            raise NoEligibleExercisesError
        policy = WorkoutGenerationPolicy.for_session_duration(
            profile.session_duration_minutes,
            warmup_minutes=self._settings.warmup_minutes,
        )
        signature = self._generation_signature(profile, candidates)
        active_plan = get_active_plan(self._db, user_id)
        if (
            active_plan is not None
            and active_plan.generation_signature == signature
            and not self._is_plan_expired(active_plan)
        ):
            return WorkoutPlanGenerationResult(plan=active_plan, reused=True)

        self._enforce_cooldown(user_id)
        request = build_workout_generation_model_request(profile, candidates, policy)
        self._enforce_request_size(request)
        generation = self._start_generation(user_id, len(candidates.exercises))
        started_at = perf_counter()
        validation_diagnostics: list[dict[str, object]] = []
        try:
            model_response = await self._generate_valid_response(
                request=request,
                candidates=candidates,
                policy=policy,
                required_day_count=profile.training_days_per_week,
                validation_diagnostics=validation_diagnostics,
            )
            refreshed_profile = self._to_generation_profile(get_profile(self._db, user_id))
            refreshed_candidates = self._select_candidates(refreshed_profile)
            if self._generation_signature(refreshed_profile, refreshed_candidates) != signature:
                raise GenerationInputsChangedError
            plan = self._build_plan(
                user_id=user_id,
                signature=signature,
                profile_snapshot=self._profile_snapshot(request),
                candidate_set_hash=candidates.candidate_set_hash,
                response=model_response.response.plan,
                policy=policy,
                model_id=model_response.model_id,
            )
            generation.model_id = model_response.model_id
            generation.provider_request_id = model_response.response.provider_request_id
            generation.input_tokens = model_response.response.input_tokens
            generation.output_tokens = model_response.response.output_tokens
            generation.latency_ms = int((perf_counter() - started_at) * 1000)
            generation.validation_diagnostics = validation_diagnostics or None
            activate_plan(self._db, plan, generation)
            self._db.commit()
            return WorkoutPlanGenerationResult(plan=plan, reused=False)
        except WorkoutProviderError as error:
            self._mark_failure(
                generation,
                error.code.value,
                error.safe_message,
                validation_diagnostics,
            )
            raise WorkoutGenerationFailedError(error.code) from None
        except WorkoutPlanValidationError:
            self._mark_failure(
                generation,
                "semantic_validation_failed",
                "Workout generation returned an invalid plan. Please try again.",
                validation_diagnostics,
            )
        except GenerationInputsChangedError:
            self._mark_failure(
                generation,
                "generation_inputs_changed",
                "Workout conditions changed while the plan was being generated. Please try again.",
                validation_diagnostics,
            )
        except SQLAlchemyError:
            self._db.rollback()
            self._mark_failure(
                generation,
                "persistence_failed",
                "Workout generation could not be saved. Please try again.",
                validation_diagnostics,
            )
        raise WorkoutGenerationFailedError

    def _start_generation(self, user_id: UUID, candidate_count: int) -> WorkoutPlanGeneration:
        try:
            generation = create_generation(
                self._db,
                user_id=user_id,
                provider=self._settings.provider_name,
                model_id=self._providers[0].model_id,
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
        validation_diagnostics: list[dict[str, object]],
    ) -> ModelGenerationResponse:
        validator = WorkoutPlanValidator(
            candidates=candidates,
            policy=policy,
            required_day_count=required_day_count,
        )
        last_error: WorkoutProviderError | WorkoutPlanValidationError | None = None
        for candidate in self._providers:
            try:
                response = await candidate.provider.generate_plan(request)
                response = replace(
                    response,
                    plan=normalize_workout_plan(response.plan, candidates),
                )
                try:
                    validator.validate(response.plan)
                    return ModelGenerationResponse(candidate.model_id, response)
                except WorkoutPlanValidationError as initial_error:
                    _log_validation_failure(candidate.model_id, "initial", initial_error)
                    validation_diagnostics.append(
                        _validation_diagnostic(candidate.model_id, "initial", initial_error)
                    )
                    if self._settings.max_repair_attempts < 1:
                        last_error = initial_error
                        continue
                    repair_request = replace(
                        request,
                        input_payload={
                            **request.input_payload,
                            "repair": {
                                "instruction": (
                                    "Return the complete plan again using the same "
                                    "allowed exercises."
                                ),
                                "validation_problems": [
                                    problem.to_repair_payload()
                                    for problem in initial_error.problems
                                ],
                            },
                        },
                    )
                    repaired = await candidate.provider.generate_plan(repair_request)
                    repaired = replace(
                        repaired,
                        plan=normalize_workout_plan(repaired.plan, candidates),
                    )
                    try:
                        validator.validate(repaired.plan)
                    except WorkoutPlanValidationError as repair_error:
                        _log_validation_failure(candidate.model_id, "repair", repair_error)
                        validation_diagnostics.append(
                            _validation_diagnostic(candidate.model_id, "repair", repair_error)
                        )
                        raise
                    return ModelGenerationResponse(candidate.model_id, repaired)
            except (WorkoutProviderError, WorkoutPlanValidationError) as error:
                last_error = error
        if last_error is not None:
            raise last_error
        raise WorkoutProviderError(
            ProviderErrorCode.PROVIDER_UNAVAILABLE,
            "Workout generation is unavailable. Please try again.",
        )

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
        policy: WorkoutGenerationPolicy,
        model_id: str,
    ) -> WorkoutPlan:

        plan = WorkoutPlan(
            user_id=user_id,
            status=WorkoutPlanStatus.GENERATING,
            generation_signature=signature,
            profile_snapshot=profile_snapshot,
            provider=self._settings.provider_name,
            model_id=model_id,
            prompt_version=self._settings.prompt_version,
            generation_policy_version=self._settings.generation_policy_version,
            candidate_set_hash=candidate_set_hash,
            generation_method="ai",
        )
        for output_day in response.days:
            timings = [
                ExerciseTiming(sets=item.sets, rest_seconds=item.rest_seconds)
                for item in output_day.exercises
            ]
            day = WorkoutDay(
                day_number=output_day.day_number,
                title_en=output_day.title_en,
                title_fa=output_day.title_fa,
                estimated_duration_minutes=policy.warmup_minutes
                + calculate_day_minutes(
                    timings,
                    set_execution_seconds=policy.set_execution_seconds,
                    transition_seconds=policy.transition_seconds_per_exercise,
                ),
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
                        estimated_minutes=calculate_exercise_minutes(
                            ExerciseTiming(
                                sets=output_exercise.sets,
                                rest_seconds=output_exercise.rest_seconds,
                            ),
                            set_execution_seconds=policy.set_execution_seconds,
                            transition_seconds=policy.transition_seconds_per_exercise,
                        ),
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
        validation_diagnostics: list[dict[str, object]],
    ) -> None:
        try:
            if generation not in self._db:
                generation = self._db.get(WorkoutPlanGeneration, generation.id) or generation
            fail_generation(
                self._db,
                generation,
                error_code=error_code,
                safe_error_message=safe_message,
                validation_diagnostics=validation_diagnostics or None,
            )
            self._db.commit()
        except SQLAlchemyError:
            self._db.rollback()

    def get_active(self, user_id: UUID) -> ActiveWorkoutPlanResult | None:
        plan = get_active_plan(self._db, user_id)
        if plan is None:
            return None
        profile = self._to_generation_profile(get_profile(self._db, user_id))
        candidates = self._select_candidates(profile)
        is_stale = plan.generation_signature != self._generation_signature(
            profile, candidates
        ) or self._is_plan_expired(plan)
        return ActiveWorkoutPlanResult(plan=plan, is_stale=is_stale)

    def _generation_signature(
        self,
        profile: WorkoutGenerationProfile,
        candidates: CandidateSet,
    ) -> str:
        return build_generation_signature(
            GenerationSignatureContext(
                fitness_goal=profile.fitness_goal,
                sex=profile.sex,
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

    def _select_candidates(self, profile: WorkoutGenerationProfile) -> CandidateSet:
        return WorkoutCandidateSelector(
            self._db,
            maximum_candidates=self._settings.max_candidates,
        ).select(profile)

    def _enforce_cooldown(self, user_id: UUID) -> None:
        if self._settings.cooldown_seconds == 0:
            return
        completed_at = get_latest_completed_generation_at(self._db, user_id)
        if completed_at is None:
            return
        elapsed = (datetime.now(UTC) - completed_at).total_seconds()
        remaining = self._settings.cooldown_seconds - elapsed
        if remaining > 0:
            raise GenerationCooldownError(ceil(remaining))

    def _enforce_request_size(self, request: WorkoutGenerationModelRequest) -> None:
        request_size = len(
            json.dumps(request.input_payload, ensure_ascii=False, separators=(",", ":")).encode()
        )
        if request_size > self._settings.max_request_bytes:
            raise WorkoutGenerationFailedError

    @staticmethod
    def plan_duration_weeks(plan: WorkoutPlan) -> int:
        value = plan.profile_snapshot.get("plan_duration_weeks")
        return value if isinstance(value, int) and value in {4, 6, 8} else 4

    @classmethod
    def _is_plan_expired(cls, plan: WorkoutPlan) -> bool:
        started_at = plan.activated_at or plan.created_at
        return datetime.now(UTC) >= started_at + timedelta(weeks=cls.plan_duration_weeks(plan))
