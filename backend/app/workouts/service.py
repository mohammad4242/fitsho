from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from math import ceil
from time import perf_counter
from typing import cast
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.ai.schemas import (
    ProviderErrorCode,
    WorkoutProviderError,
)
from app.body_analysis.providers import ProviderRoutingPreferences
from app.exercises.enums import (
    Equipment,
    ExerciseCautionTag,
    ExerciseContentType,
    MediaPresentation,
    MuscleGroup,
)
from app.exercises.models import Exercise
from app.exercises.programming_metadata import infer_exercise_demands
from app.profile.enums import ExperienceLevel, HomeTrainingSetup, Sex, TrainingLocation
from app.profile.service import ProfileSnapshot, get_profile
from app.profile.training_compatibility import (
    UnsupportedResistanceTrainingCombinationError,
    require_supported_resistance_training_days,
)
from app.training_templates.engine_reference import load_template_references
from app.workout_cycles.enums import WorkoutCycleStatus
from app.workout_cycles.models import WorkoutCycle, WorkoutCycleWeeklyCheckIn
from app.workouts.ai_coach import (
    AiCoachProgramCandidate,
    candidate_program_payload,
    select_ai_coach_candidates,
)
from app.workouts.ai_coach_provider import (
    AiCoachRecommendation,
    AiCoachRecommendationRequest,
    OpenRouterAiCoachProvider,
)
from app.workouts.body_analysis_resolver import (
    BodyAnalysisInfluenceResolver,
    WorkoutBodyAnalysisResolver,
)
from app.workouts.candidate_selector import (
    WorkoutCandidateSelector,
    caution_tags_for_training_cautions,
)
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanExercise, WorkoutPlanGeneration
from app.workouts.program_engine.body_analysis import applicable_body_analysis_influence
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import (
    BodyPosition,
    GenerationErrorCode,
    ImpactLimit,
    Laterality,
    LoadLimit,
    SkillDemand,
    StabilityDemand,
    TrainingExperience,
)
from app.workouts.program_engine.equipment import effective_required_equipment
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET, ProgramRuleset
from app.workouts.program_engine.schemas import (
    BodyAnalysisInfluence,
    ExerciseCandidate,
    Limitation,
    ProgramGenerationRequest,
    RecentTrainingHistory,
    TemplateReference,
    WorkoutProgram,
)
from app.workouts.program_engine.session_targets import persian_session_title
from app.workouts.repository import (
    create_generation,
    fail_generation,
    get_active_plan,
    get_latest_completed_generation_at,
    persist_pending_review_plan,
)
from app.workouts.schemas import CandidateSet, ProgramGenerationOverrides, WorkoutGenerationProfile
from app.workouts.signature import (
    build_generation_request_signature,
    normalize_physical_limitations,
)
from app.workouts.time_budget import (
    ExerciseTiming,
    calculate_day_minutes,
    calculate_exercise_minutes,
)
from app.workouts.validator import WorkoutPlanValidationError


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
    deterministic_fallback_enabled: bool = True
    generation_method: str = "fitsho_coach"
    ai_coach_fallback_models: tuple[str, ...] = ()
    ai_coach_temperature: float = 0.0
    ai_coach_max_output_tokens: int = 4096
    ai_coach_routing_preferences: ProviderRoutingPreferences = ProviderRoutingPreferences()


@dataclass(frozen=True)
class _LegacyExerciseProgrammingMetadata:
    """Conservative mapping for catalog rows predating persisted metadata."""

    body_position: BodyPosition
    stability_demand: StabilityDemand
    skill_demand: SkillDemand
    impact_level: ImpactLimit
    axial_loading_level: LoadLimit
    fatigue_cost: int
    setup_cost: int
    laterality: Laterality
    substitution_group: str
    range_of_motion_profile: frozenset[str]


def legacy_training_age_months(experience_level: ExperienceLevel) -> int:
    """Temporary fallback for profiles created before training age was persisted."""
    return {
        ExperienceLevel.FIRST_MONTH: 0,
        ExperienceLevel.BEGINNER: 0,
        ExperienceLevel.INTERMEDIATE: 12,
        ExperienceLevel.ADVANCED: 48,
    }[experience_level]


@dataclass(frozen=True)
class WorkoutPlanGenerationResult:
    plan: WorkoutPlan
    reused: bool


@dataclass(frozen=True)
class ActiveWorkoutPlanResult:
    plan: WorkoutPlan
    is_stale: bool


class GenerationInProgressError(Exception):
    pass


class GenerationCooldownError(Exception):
    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds


class NoEligibleExercisesError(Exception):
    def __init__(self, error_code: str = "INSUFFICIENT_ELIGIBLE_EXERCISES") -> None:
        self.error_code = error_code


class WorkoutConstructionUnsatisfiedError(Exception):
    def __init__(self, error_code: str = "UNSATISFIED_CONSTRAINT") -> None:
        self.error_code = error_code


class ProgramGenerationRejectedError(Exception):
    def __init__(self, error_code: str, safety_status: str | None = None) -> None:
        self.error_code = error_code
        self.safety_status = safety_status


class WorkoutGenerationFailedError(Exception):
    def __init__(
        self,
        provider_error_code: ProviderErrorCode | None = None,
        *,
        error_code: str | None = None,
    ) -> None:
        self.provider_error_code = provider_error_code
        self.error_code = error_code


class WorkoutGenerationService:
    def __init__(
        self,
        db: Session,
        *,
        ai_coach_provider: OpenRouterAiCoachProvider | None = None,
        settings: WorkoutGenerationSettings,
        ruleset: ProgramRuleset = RULESET,
        body_analysis_resolver: BodyAnalysisInfluenceResolver | None = None,
    ) -> None:
        self._db = db
        self._ai_coach_provider = ai_coach_provider
        self._settings = settings
        self._ruleset = ruleset
        self._body_analysis_resolver = body_analysis_resolver or WorkoutBodyAnalysisResolver(db)

    async def generate(
        self,
        user_id: UUID,
        overrides: ProgramGenerationOverrides | None = None,
    ) -> WorkoutPlanGenerationResult:
        if self._settings.generation_method == "ai":
            return await self._generate_with_ai(user_id)
        return await self._generate_deterministic(user_id, overrides)

    async def _generate_deterministic(
        self,
        user_id: UUID,
        overrides: ProgramGenerationOverrides | None = None,
        *,
        generation: WorkoutPlanGeneration | None = None,
        fallback_reason_code: str | None = None,
    ) -> WorkoutPlanGenerationResult:
        source_profile = get_profile(self._db, user_id)
        effective_overrides = self._with_previous_volume_history(user_id, overrides)
        body_analysis_influence = applicable_body_analysis_influence(
            self._body_analysis_resolver.resolve(user_id), self._ruleset
        )
        try:
            request = self._to_program_request(
                source_profile, effective_overrides, body_analysis_influence
            )
        except UnsupportedResistanceTrainingCombinationError as error:
            raise ProgramGenerationRejectedError("UNSUPPORTED_RESISTANCE_TRAINING_DAYS") from error
        except ValidationError as error:
            raise ProgramGenerationRejectedError("INVALID_PROFILE_INPUT") from error
        catalog = self._load_catalog(source_profile.profile.sex)
        catalog_hash = self._catalog_hash(catalog)
        references = load_template_references(self._db)
        reference_hash = self._template_reference_hash(references)
        signature = self._generation_signature(request, catalog_hash, reference_hash)
        active_plan = get_active_plan(self._db, user_id)
        if (
            active_plan is not None
            and active_plan.generation_signature == signature
            and not self._is_plan_expired(active_plan)
        ):
            return WorkoutPlanGenerationResult(plan=active_plan, reused=True)

        self._enforce_cooldown(user_id)
        if generation is None:
            generation = self._start_generation(user_id, len(catalog))
        else:
            generation.candidate_count = len(catalog)
        started_at = perf_counter()
        result = generate_program(
            request,
            catalog,
            self._ruleset,
            reference_templates=references,
        )
        if not result.is_success or result.program is None:
            error_code = (
                result.error_code.value
                if result.error_code is not None
                else GenerationErrorCode.PROGRAM_VALIDATION_FAILED.value
            )
            safe_message, problem_message = _generation_failure_messages(result.error_code)
            self._mark_failure(
                generation,
                error_code,
                safe_message,
                [
                    {
                        "model_id": self._ruleset.engine_version,
                        "phase": "initial",
                        "problems": [
                            {
                                "code": error,
                                "message": problem_message,
                            }
                            for error in result.errors
                        ],
                        **(
                            {"decision_trace": _json_ready(result.decision_trace)}
                            if result.decision_trace
                            else {}
                        ),
                    }
                ],
            )
            if result.error_code is GenerationErrorCode.UNSATISFIED_CONSTRAINT:
                raise WorkoutConstructionUnsatisfiedError(error_code)
            if result.error_code in {
                GenerationErrorCode.NO_SAFE_EXERCISE_FOR_PATTERN,
                GenerationErrorCode.NO_AVAILABLE_EQUIPMENT_MATCH,
                GenerationErrorCode.INSUFFICIENT_ELIGIBLE_EXERCISES,
            }:
                raise NoEligibleExercisesError(error_code)
            if result.error_code is GenerationErrorCode.PROGRAM_REJECTED_SAFETY_STATUS:
                raise ProgramGenerationRejectedError(
                    error_code,
                    result.safety_status.value if result.safety_status else None,
                )
            if result.error_code is GenerationErrorCode.UNSUPPORTED_RESISTANCE_TRAINING_DAYS:
                raise ProgramGenerationRejectedError(error_code)
            raise WorkoutGenerationFailedError(error_code=error_code)

        refreshed_profile = get_profile(self._db, user_id)
        refreshed_request = self._to_program_request(
            refreshed_profile,
            effective_overrides,
            applicable_body_analysis_influence(
                self._body_analysis_resolver.resolve(user_id), self._ruleset
            ),
        )
        refreshed_catalog = self._load_catalog(refreshed_profile.profile.sex)
        if (
            self._generation_signature(
                refreshed_request,
                self._catalog_hash(refreshed_catalog),
                self._template_reference_hash(load_template_references(self._db)),
            )
            != signature
        ):
            self._mark_failure(
                generation,
                "generation_inputs_changed",
                "Workout conditions changed during generation. Please try again.",
                [],
            )
            raise WorkoutGenerationFailedError(error_code="generation_inputs_changed")

        try:
            plan = self._build_plan(
                user_id=user_id,
                signature=signature,
                catalog_hash=catalog_hash,
                catalog=catalog,
                program=result.program,
                previous=active_plan,
            )
            if fallback_reason_code is not None:
                plan.warnings = [*plan.warnings, "AI_REASONING_FALLBACK"]
                plan.decision_trace = [
                    *plan.decision_trace,
                    {
                        "stage": "ai_reasoning",
                        "status": "fallback",
                        "reason_code": fallback_reason_code,
                        "source": "deterministic_domain",
                        "ai_output_persisted": False,
                    },
                ]
            generation.provider = "fitsho_domain"
            generation.model_id = result.program.engine_version
            generation.latency_ms = int((perf_counter() - started_at) * 1000)
            generation.validation_diagnostics = [
                cast(dict[str, object], _json_ready(asdict(result.program.validation_report)))
            ]
            persist_pending_review_plan(self._db, plan, generation)
            self._db.commit()
            return WorkoutPlanGenerationResult(plan=plan, reused=False)
        except SQLAlchemyError as error:
            self._db.rollback()
            self._mark_failure(
                generation,
                "persistence_failed",
                "Workout generation could not be saved. Please try again.",
                [],
            )
            raise WorkoutGenerationFailedError(error_code="persistence_failed") from error

    def _with_previous_volume_history(
        self,
        user_id: UUID,
        overrides: ProgramGenerationOverrides | None,
    ) -> ProgramGenerationOverrides | None:
        if overrides is not None and overrides.recent_training_history is not None:
            return overrides
        history = self._previous_volume_history(user_id)
        if history is None:
            return overrides
        if overrides is None:
            return ProgramGenerationOverrides(recent_training_history=history)
        return overrides.model_copy(update={"recent_training_history": history})

    def _previous_volume_history(self, user_id: UUID) -> RecentTrainingHistory | None:
        cycle = self._db.scalar(
            select(WorkoutCycle)
            .where(
                WorkoutCycle.user_id == user_id,
                WorkoutCycle.status == WorkoutCycleStatus.COMPLETED,
            )
            .options(
                selectinload(WorkoutCycle.workout_plan).selectinload(WorkoutPlan.days),
                selectinload(WorkoutCycle.completion_feedback),
            )
            .order_by(WorkoutCycle.completed_at.desc(), WorkoutCycle.id.desc())
            .limit(1)
        )
        if cycle is None or cycle.workout_plan is None:
            return None

        check_ins = list(
            self._db.scalars(
                select(WorkoutCycleWeeklyCheckIn)
                .where(
                    WorkoutCycleWeeklyCheckIn.user_id == user_id,
                    WorkoutCycleWeeklyCheckIn.cycle_id == cycle.id,
                )
                .order_by(WorkoutCycleWeeklyCheckIn.week_number, WorkoutCycleWeeklyCheckIn.id)
            ).all()
        )
        adherence = self._previous_cycle_adherence(cycle, check_ins)
        if adherence is None or adherence <= 0:
            return None

        metrics = cycle.workout_plan.aggregate_metrics
        direct = self._volume_metrics(
            metrics.get("weekly_direct_sets_by_muscle")
            or metrics.get("planned_direct_sets_by_muscle")
        )
        effective = self._volume_metrics(metrics.get("weekly_effective_sets_by_muscle"))
        if not direct and not effective:
            return None
        return RecentTrainingHistory(
            completed_session_ratio=adherence,
            previous_weekly_direct_sets_by_muscle=direct,
            previous_weekly_effective_sets_by_muscle=effective,
            previous_volume_confidence=adherence,
            previous_volume_source="prescribed_plan",
            previous_volume_reason_codes=(
                "HISTORY_FROM_COMPLETED_PLAN",
                "HISTORY_SCALED_BY_ADHERENCE",
            ),
        )

    @staticmethod
    def _previous_cycle_adherence(
        cycle: WorkoutCycle,
        check_ins: list[WorkoutCycleWeeklyCheckIn],
    ) -> float | None:
        prescribed_sessions = len(cycle.workout_plan.days) if cycle.workout_plan else 0
        if check_ins and prescribed_sessions > 0:
            planned = prescribed_sessions * len(check_ins)
            completed = sum(item.sessions_completed for item in check_ins)
            return round(min(1.0, max(0.0, completed / planned)), 2)
        feedback = cycle.completion_feedback
        if feedback is not None and feedback.adherence_percent is not None:
            return round(min(1.0, max(0.0, feedback.adherence_percent / 100)), 2)
        return None

    @staticmethod
    def _volume_metrics(value: object) -> dict[MuscleGroup, float]:
        if not isinstance(value, dict):
            return {}
        metrics: dict[MuscleGroup, float] = {}
        for raw_muscle, raw_sets in value.items():
            try:
                muscle = MuscleGroup(raw_muscle)
                sets = float(raw_sets)
            except (TypeError, ValueError):
                continue
            if sets > 0:
                metrics[muscle] = round(sets, 2)
        return metrics

    async def _generate_with_ai(self, user_id: UUID) -> WorkoutPlanGenerationResult:
        if self._ai_coach_provider is None:
            if self._settings.deterministic_fallback_enabled:
                return await self._generate_deterministic(
                    user_id,
                    fallback_reason_code="AI_PROVIDER_UNAVAILABLE",
                )
            raise WorkoutGenerationFailedError(error_code="no_enabled_ai_model")
        source_profile = get_profile(self._db, user_id)
        profile = self._to_generation_profile(source_profile)
        eligible_exercises = WorkoutCandidateSelector(self._db, maximum_candidates=None).select(
            profile
        )
        if not eligible_exercises.is_sufficient:
            if self._settings.deterministic_fallback_enabled:
                return await self._generate_deterministic(
                    user_id,
                    fallback_reason_code="DETERMINISTIC_INPUT_UNAVAILABLE",
                )
            raise NoEligibleExercisesError("INSUFFICIENT_ELIGIBLE_EXERCISES")
        body_analysis = applicable_body_analysis_influence(
            self._body_analysis_resolver.resolve(user_id), self._ruleset
        )
        library_candidates = select_ai_coach_candidates(
            templates=load_template_references(self._db),
            profile=profile,
            eligible_exercise_ids=frozenset(eligible_exercises.ids),
            priority_muscles=(
                tuple(priority.muscle for priority in body_analysis.priorities)
                if body_analysis is not None
                else ()
            ),
        )
        if len(library_candidates) < 2:
            if self._settings.deterministic_fallback_enabled:
                return await self._generate_deterministic(
                    user_id,
                    fallback_reason_code="AI_CANDIDATES_UNAVAILABLE",
                )
            raise WorkoutGenerationFailedError(error_code="insufficient_library_programs")
        signature = self._ai_coach_generation_signature(
            profile, library_candidates, eligible_exercises
        )
        active_plan = get_active_plan(self._db, user_id)
        if (
            active_plan is not None
            and active_plan.generation_signature == signature
            and not self._is_plan_expired(active_plan)
        ):
            return WorkoutPlanGenerationResult(plan=active_plan, reused=True)
        self._enforce_cooldown(user_id)
        catalog = {item.id: item for item in self._load_catalog(profile.sex)}
        payloads = tuple(
            candidate_program_payload(
                candidate,
                exercise_names_fa={
                    exercise_id: str(catalog[exercise_id].display_snapshot["name_fa"])
                    for day in candidate.template.days
                    for slot in day.slots
                    if (exercise_id := slot.exercise_id) is not None
                },
            )
            for candidate in library_candidates
        )
        profile_payload = self._ai_coach_profile_payload(profile, body_analysis)
        request_size = len(
            json.dumps(
                {"profile": profile_payload, "candidate_programs": payloads},
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
        )
        if request_size > self._settings.max_request_bytes:
            if self._settings.deterministic_fallback_enabled:
                return await self._generate_deterministic(
                    user_id,
                    fallback_reason_code="AI_REQUEST_TOO_LARGE",
                )
            raise WorkoutGenerationFailedError(error_code="request_too_large")
        generation = self._start_generation(user_id, len(library_candidates))
        started_at = perf_counter()
        try:
            recommendation = await self._ai_coach_provider.recommend(
                AiCoachRecommendationRequest(
                    profile=profile_payload,
                    candidate_programs=payloads,
                    primary_model=self._settings.model_id,
                    fallback_models=self._settings.ai_coach_fallback_models,
                    temperature=self._settings.ai_coach_temperature,
                    max_output_tokens=self._settings.ai_coach_max_output_tokens,
                    routing_preferences=self._settings.ai_coach_routing_preferences,
                )
            )
            if not isinstance(recommendation, AiCoachRecommendation):
                raise ValueError("AI coach returned an invalid recommendation object")
        except WorkoutProviderError as error:
            if self._settings.deterministic_fallback_enabled:
                return await self._generate_deterministic(
                    user_id,
                    generation=generation,
                    fallback_reason_code=error.code.value.upper(),
                )
            self._mark_failure(generation, error.code.value, error.safe_message, [])
            raise WorkoutGenerationFailedError(error.code) from None
        except Exception:
            if self._settings.deterministic_fallback_enabled:
                return await self._generate_deterministic(
                    user_id,
                    generation=generation,
                    fallback_reason_code="AI_OUTPUT_INVALID",
                )
            self._mark_failure(
                generation,
                ProviderErrorCode.INVALID_OUTPUT.value,
                "Workout generation returned an invalid AI response.",
                [],
            )
            raise WorkoutGenerationFailedError(
                error_code=ProviderErrorCode.INVALID_OUTPUT.value
            ) from None
        try:
            selected = next(
                candidate
                for candidate in library_candidates
                if candidate.template.slug == recommendation.selected_candidate_id
            )
            plan = self._build_ai_coach_plan(
                user_id=user_id,
                signature=signature,
                profile=profile,
                candidate_set_hash=eligible_exercises.candidate_set_hash,
                candidate=selected,
                catalog=catalog,
                recommendation=recommendation,
                body_analysis=body_analysis,
            )
            generation.provider = self._settings.provider_name
            generation.model_id = recommendation.model_id
            generation.provider_request_id = recommendation.provider_request_id
            generation.input_tokens = recommendation.input_tokens
            generation.output_tokens = recommendation.output_tokens
            generation.latency_ms = int((perf_counter() - started_at) * 1000)
            persist_pending_review_plan(self._db, plan, generation)
            self._db.commit()
            return WorkoutPlanGenerationResult(plan=plan, reused=False)
        except WorkoutProviderError as error:
            if self._settings.deterministic_fallback_enabled:
                return await self._generate_deterministic(
                    user_id,
                    generation=generation,
                    fallback_reason_code=error.code.value.upper(),
                )
            self._mark_failure(generation, error.code.value, error.safe_message, [])
            raise WorkoutGenerationFailedError(error.code) from None
        except WorkoutPlanValidationError as error:
            if self._settings.deterministic_fallback_enabled:
                return await self._generate_deterministic(
                    user_id,
                    generation=generation,
                    fallback_reason_code="AI_SCHEMA_INVALID",
                )
            self._mark_failure(
                generation,
                "semantic_validation_failed",
                "Workout generation returned an invalid plan. Please try again.",
                [{"errors": [problem.code for problem in error.problems]}],
            )
            raise WorkoutGenerationFailedError(error_code="semantic_validation_failed") from None
        except (StopIteration, ValueError, ValidationError):
            if self._settings.deterministic_fallback_enabled:
                return await self._generate_deterministic(
                    user_id,
                    generation=generation,
                    fallback_reason_code="AI_OUTPUT_INVALID",
                )
            self._mark_failure(
                generation,
                ProviderErrorCode.INVALID_OUTPUT.value,
                "Workout generation returned an invalid AI response.",
                [],
            )
            raise WorkoutGenerationFailedError(
                error_code=ProviderErrorCode.INVALID_OUTPUT.value
            ) from None

    def _build_ai_coach_plan(
        self,
        *,
        user_id: UUID,
        signature: str,
        profile: WorkoutGenerationProfile,
        candidate_set_hash: str,
        candidate: AiCoachProgramCandidate,
        catalog: dict[UUID, ExerciseCandidate],
        recommendation: AiCoachRecommendation,
        body_analysis: BodyAnalysisInfluence | None,
    ) -> WorkoutPlan:
        snapshots = {str(item.id): self._candidate_snapshot(item) for item in catalog.values()}
        day_notes = {
            item.day_number: item.explanation_fa for item in recommendation.day_explanations
        }
        plan = WorkoutPlan(
            user_id=user_id,
            status=WorkoutPlanStatus.GENERATING,
            generation_signature=signature,
            profile_snapshot={
                "goal": str(profile.fitness_goal),
                "experience_level": profile.experience_level.value,
                "training_days_per_week": profile.training_days_per_week,
                "session_duration_minutes": profile.session_duration_minutes,
                "plan_duration_weeks": profile.plan_duration_weeks,
            },
            provider=self._settings.provider_name,
            model_id=recommendation.model_id,
            prompt_version=self._settings.prompt_version,
            generation_policy_version=self._settings.generation_policy_version,
            candidate_set_hash=candidate_set_hash,
            generation_method="ai",
            engine_version="template_library_v1",
            ruleset_version="template_library_v1",
            primary_goal=str(profile.fitness_goal),
            training_status=profile.experience_level.value,
            safety_status="template_eligible",
            exercise_catalog_snapshot={"hash": candidate_set_hash, "exercises": snapshots},
            body_analysis_provenance=(
                _json_ready(body_analysis.model_dump(mode="json")) if body_analysis else {}
            ),
            ai_coach_template_slug=candidate.template.slug,
            ai_coach_program_explanation_fa=recommendation.program_explanation_fa,
        )
        for template_day in candidate.template.days:
            timings = [ExerciseTiming(slot.sets, slot.rest_seconds) for slot in template_day.slots]
            day = WorkoutDay(
                day_number=template_day.day_number,
                title_en=template_day.title,
                title_fa=template_day.title_fa or template_day.title,
                focus=", ".join(muscle.value for muscle in template_day.focus),
                estimated_duration_minutes=(
                    self._settings.warmup_minutes + calculate_day_minutes(timings)
                ),
                ai_coach_explanation_fa=day_notes.get(template_day.day_number),
            )
            for order, slot in enumerate(template_day.slots, start=1):
                if slot.exercise_id is None:
                    raise ValueError("AI coach candidate has an unresolved exercise")
                day.exercises.append(
                    WorkoutPlanExercise(
                        exercise_id=slot.exercise_id,
                        order_index=order,
                        sets=slot.sets,
                        prescription_mode="reps",
                        reps_min=slot.rep_min,
                        reps_max=slot.rep_max,
                        duration_min_seconds=None,
                        duration_max_seconds=None,
                        rest_seconds=slot.rest_seconds,
                        rir=slot.target_rir,
                        estimated_minutes=calculate_exercise_minutes(
                            ExerciseTiming(slot.sets, slot.rest_seconds)
                        ),
                        exercise_snapshot=snapshots[str(slot.exercise_id)],
                    )
                )
            plan.days.append(day)
        return plan

    def _ai_coach_generation_signature(
        self,
        profile: WorkoutGenerationProfile,
        candidates: tuple[AiCoachProgramCandidate, ...],
        eligible_exercises: CandidateSet,
    ) -> str:
        payload = {
            "profile": self._ai_coach_profile_payload(profile, None),
            "candidate_set_hash": eligible_exercises.candidate_set_hash,
            "templates": [item.template.slug for item in candidates],
            "model": self._settings.model_id,
            "prompt": self._settings.prompt_version,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _ai_coach_profile_payload(
        profile: WorkoutGenerationProfile,
        body_analysis: BodyAnalysisInfluence | None,
    ) -> dict[str, object]:
        return {
            "fitness_goal": str(profile.fitness_goal),
            "experience_level": profile.experience_level.value,
            "training_days_per_week": profile.training_days_per_week,
            "session_duration_minutes": profile.session_duration_minutes,
            "training_location": profile.training_location.value,
            "training_cautions": [item.value for item in profile.training_cautions],
            "physical_limitations": profile.physical_limitations,
            "body_analysis_priorities": (
                [priority.model_dump(mode="json") for priority in body_analysis.priorities]
                if body_analysis is not None
                else []
            ),
        }

    def _to_generation_profile(self, source: ProfileSnapshot) -> WorkoutGenerationProfile:
        profile = source.profile
        assert profile.fitness_goal is not None
        assert profile.experience_level is not None
        assert profile.training_days_per_week is not None
        assert profile.training_location is not None
        assert profile.session_duration_minutes is not None
        assert profile.plan_duration_weeks is not None
        assert profile.birth_date is not None
        assert profile.sex is not None
        assert profile.height_cm is not None
        return WorkoutGenerationProfile(
            fitness_goal=profile.fitness_goal,
            experience_level=profile.experience_level,
            training_days_per_week=profile.training_days_per_week,
            training_location=profile.training_location,
            home_training_setup=profile.home_training_setup,
            session_duration_minutes=profile.session_duration_minutes,
            plan_duration_weeks=profile.plan_duration_weeks,
            training_cautions=tuple(
                sorted(
                    (item.caution for item in profile.training_caution_items),
                    key=lambda item: item.value,
                )
            ),
            physical_limitations=self._sanitize_limitations(profile.physical_limitations),
            current_weight_kg=source.measurement.weight_kg,
            age=self._age(profile.birth_date),
            sex=profile.sex,
            height_cm=profile.height_cm,
        )

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

    def _build_plan(
        self,
        *,
        user_id: UUID,
        signature: str,
        catalog_hash: str,
        catalog: tuple[ExerciseCandidate, ...],
        program: WorkoutProgram,
        previous: WorkoutPlan | None,
    ) -> WorkoutPlan:
        snapshots = {str(item.id): self._candidate_snapshot(item) for item in catalog}
        plan = WorkoutPlan(
            user_id=user_id,
            status=WorkoutPlanStatus.GENERATING,
            generation_signature=signature,
            profile_snapshot=program.user_profile_snapshot,
            provider="fitsho_domain",
            model_id=program.engine_version,
            prompt_version="none",
            generation_policy_version=program.ruleset_version,
            candidate_set_hash=catalog_hash,
            generation_method="deterministic_domain",
            engine_version=program.engine_version,
            ruleset_version=program.ruleset_version,
            primary_goal=program.primary_goal.value,
            secondary_goal=program.secondary_goal.value if program.secondary_goal else None,
            training_status=program.training_status.value,
            safety_status=program.safety_status.value,
            seed=program.seed,
            exercise_catalog_snapshot={"hash": catalog_hash, "exercises": snapshots},
            assumptions=list(program.assumptions),
            warnings=list(program.warnings),
            validation_report=_json_ready(asdict(program.validation_report)),
            aggregate_metrics=_json_ready(program.aggregate_metrics),
            decision_trace=_json_ready(program.decision_trace),
            body_analysis_provenance=_json_ready(program.body_analysis_provenance),
            progression_policy=_json_ready(program.progression_policy),
            previous_program_id=previous.id if previous else None,
            regeneration_reason="inputs_or_program_expired" if previous else None,
            difference_summary=(
                {
                    "previous_program_id": str(previous.id),
                    "generation_signature_changed": previous.generation_signature != signature,
                    "ruleset_changed": previous.ruleset_version != program.ruleset_version,
                    "catalog_changed": previous.candidate_set_hash != catalog_hash,
                }
                if previous
                else {}
            ),
        )
        for output_day in program.weekly_schedule:
            day = WorkoutDay(
                day_number=output_day.day_index,
                weekday=output_day.weekday,
                title_en=output_day.title,
                title_fa=persian_session_title(output_day.day_index, output_day.exercises),
                focus=output_day.focus,
                cardio=_json_ready(asdict(output_day.cardio)) if output_day.cardio else None,
                estimated_duration_minutes=output_day.estimated_duration_minutes,
            )
            for item in output_day.exercises:
                day.exercises.append(
                    WorkoutPlanExercise(
                        exercise_id=item.exercise_id,
                        order_index=item.order,
                        sets=item.sets,
                        prescription_mode=item.prescription_mode,
                        reps_min=item.rep_min,
                        reps_max=item.rep_max,
                        duration_min_seconds=item.duration_min_seconds,
                        duration_max_seconds=item.duration_max_seconds,
                        rest_seconds=item.rest_seconds,
                        rir=item.target_rir,
                        estimated_minutes=item.estimated_minutes,
                        notes_en=item.notes,
                        notes_fa=None,
                        exercise_snapshot=snapshots[str(item.exercise_id)],
                        reason_codes=list(item.reason_codes),
                        substitution_exercise_ids=[
                            str(exercise_id) for exercise_id in item.substitution_exercise_ids
                        ],
                        warmup_sets=item.warmup_sets,
                        load_guidance=item.load_guidance,
                        progression_rule=item.progression_rule,
                    )
                )
            plan.days.append(day)
        return plan

    def _to_program_request(
        self,
        source: ProfileSnapshot,
        overrides: ProgramGenerationOverrides | None,
        body_analysis_influence: BodyAnalysisInfluence | None = None,
    ) -> ProgramGenerationRequest:
        profile = source.profile
        assert profile.training_location is not None
        assert profile.experience_level is not None
        assert profile.birth_date is not None
        assert profile.sex is not None
        assert profile.height_cm is not None
        assert profile.fitness_goal is not None
        assert profile.training_days_per_week is not None
        assert profile.session_duration_minutes is not None
        assert profile.plan_duration_weeks is not None
        equipment = self._available_equipment(
            profile.training_location,
            profile.home_training_setup,
        )
        cautions = tuple(item.caution for item in profile.training_caution_items)
        blocked_caution_tags = caution_tags_for_training_cautions(cautions)
        sanitized = self._sanitize_limitations(profile.physical_limitations)
        limitations = (Limitation(name=sanitized, stable=False),) if sanitized is not None else ()
        training_age = (
            profile.training_age_months
            if profile.training_age_months is not None
            else legacy_training_age_months(profile.experience_level)
        )
        values: dict[str, object] = {
            "user_id": profile.user_id,
            "age": self._age(profile.birth_date),
            "biological_sex_optional": profile.sex.value,
            "height_cm": profile.height_cm,
            "weight_kg": float(source.measurement.weight_kg),
            "primary_goal": profile.fitness_goal.value,
            "training_experience": TrainingExperience(profile.experience_level.value),
            "training_age_months": training_age,
            "available_training_days": profile.training_days_per_week,
            "preferred_weekdays": tuple(profile.preferred_weekdays or ()),
            "priority_muscles": frozenset(
                MuscleGroup(value) for value in (profile.priority_muscles or ())
            ),
            "session_duration_minutes": profile.session_duration_minutes,
            "available_equipment": equipment,
            "training_location": profile.training_location,
            "injuries_and_limitations": limitations,
            "blocked_caution_tags": blocked_caution_tags,
            "program_duration_weeks": profile.plan_duration_weeks,
            "body_analysis_influence": body_analysis_influence,
        }
        if overrides is not None:
            override_values = overrides.model_dump(exclude_none=True)
            if (
                "priority_muscles" not in overrides.model_fields_set
                and not overrides.priority_muscles
            ):
                override_values.pop("priority_muscles", None)
            if "blocked_caution_tags" in override_values:
                values["blocked_caution_tags"] = frozenset(
                    cast(frozenset[ExerciseCautionTag], values["blocked_caution_tags"])
                ) | frozenset(
                    cast(
                        frozenset[ExerciseCautionTag],
                        override_values.pop("blocked_caution_tags"),
                    )
                )
            values.update(override_values)
            values["user_id"] = profile.user_id
        require_supported_resistance_training_days(
            profile.experience_level,
            cast(int, values["available_training_days"]),
        )
        return ProgramGenerationRequest.model_validate(values)

    def _load_catalog(self, profile_sex: Sex | None = None) -> tuple[ExerciseCandidate, ...]:
        exercises = self._db.scalars(
            select(Exercise)
            .where(Exercise.content_type == ExerciseContentType.EXERCISE)
            .options(
                selectinload(Exercise.secondary_muscles),
                selectinload(Exercise.equipment_items),
                selectinload(Exercise.caution_tag_items),
                selectinload(Exercise.labels),
                selectinload(Exercise.media_assets),
            )
        ).all()
        return tuple(
            sorted(
                (self._domain_candidate(item, profile_sex) for item in exercises),
                key=lambda item: str(item.id),
            )
        )

    @staticmethod
    def _domain_candidate(exercise: Exercise, profile_sex: Sex | None = None) -> ExerciseCandidate:
        caution_tags = frozenset(item.caution_tag for item in exercise.caution_tag_items)
        selected_media = WorkoutGenerationService._selected_media(exercise, profile_sex)
        legacy = WorkoutGenerationService._legacy_candidate_metadata(exercise, caution_tags)
        secondary_muscles = tuple(
            sorted(
                (item.muscle for item in exercise.secondary_muscles),
                key=lambda muscle: muscle.value,
            )
        )
        range_of_motion_profile = (
            frozenset(exercise.range_of_motion_profile)
            if exercise.range_of_motion_profile is not None
            else legacy.range_of_motion_profile
        )
        return ExerciseCandidate(
            id=exercise.id,
            name=exercise.name_en,
            primary_muscle=exercise.primary_muscle,
            secondary_muscles=secondary_muscles,
            movement_pattern=exercise.movement_pattern,
            exercise_type=exercise.exercise_type,
            equipment=effective_required_equipment(
                (item.equipment for item in exercise.equipment_items),
                exercise.movement_pattern,
            ),
            difficulty=exercise.difficulty,
            caution_tags=caution_tags,
            labels=frozenset(item.label for item in exercise.labels),
            is_active=exercise.is_active,
            is_programmable=exercise.is_programmable,
            needs_review=exercise.needs_review,
            body_position=(
                exercise.body_position
                if exercise.body_position is not None
                else legacy.body_position
            ),
            stability_demand=(
                exercise.stability_demand
                if exercise.stability_demand is not None
                else legacy.stability_demand
            ),
            skill_demand=(
                exercise.skill_demand if exercise.skill_demand is not None else legacy.skill_demand
            ),
            impact_level=(
                exercise.impact_level if exercise.impact_level is not None else legacy.impact_level
            ),
            axial_loading_level=(
                exercise.axial_loading_level
                if exercise.axial_loading_level is not None
                else legacy.axial_loading_level
            ),
            fatigue_cost=(
                exercise.fatigue_cost if exercise.fatigue_cost is not None else legacy.fatigue_cost
            ),
            setup_cost=(
                exercise.setup_cost if exercise.setup_cost is not None else legacy.setup_cost
            ),
            laterality=(
                exercise.laterality if exercise.laterality is not None else legacy.laterality
            ),
            range_of_motion_profile=range_of_motion_profile,
            substitution_group=(
                exercise.substitution_group
                if exercise.substitution_group is not None
                else legacy.substitution_group
            ),
            display_snapshot={
                "id": str(exercise.id),
                "slug": exercise.slug,
                "name_en": exercise.name_en,
                "name_fa": exercise.name_fa,
                "body_region": exercise.body_region.value if exercise.body_region else None,
                "primary_muscle": (
                    exercise.primary_muscle.value if exercise.primary_muscle else None
                ),
                "labels": sorted(item.label.value for item in exercise.labels),
                "secondary_muscles": sorted(
                    item.muscle.value for item in exercise.secondary_muscles
                ),
                "equipment": sorted(item.equipment.value for item in exercise.equipment_items),
                "difficulty": exercise.difficulty.value,
                "media_path": selected_media[0],
                "media_type": selected_media[1],
            },
            prescription_mode=exercise.prescription_mode,
            duration_min_seconds=exercise.duration_min_seconds,
            duration_max_seconds=exercise.duration_max_seconds,
        )

    @staticmethod
    def _legacy_candidate_metadata(
        exercise: Exercise,
        caution_tags: frozenset[ExerciseCautionTag],
    ) -> _LegacyExerciseProgrammingMetadata:
        """Infer only the legacy defaults needed by incomplete catalog rows."""

        demands = infer_exercise_demands(exercise)
        return _LegacyExerciseProgrammingMetadata(
            body_position=demands.body_position,
            stability_demand=demands.stability_demand,
            skill_demand=demands.skill_demand,
            impact_level=demands.impact_level,
            axial_loading_level=(
                LoadLimit.HIGH
                if ExerciseCautionTag.LOWER_BACK_LOADING in caution_tags
                else LoadLimit.LOW
            ),
            fatigue_cost=demands.fatigue_cost,
            setup_cost=demands.setup_cost,
            laterality=Laterality.BILATERAL,
            substitution_group=exercise.movement_pattern.value,
            range_of_motion_profile=(
                frozenset({"deep_knee_flexion"})
                if ExerciseCautionTag.DEEP_KNEE_FLEXION in caution_tags
                else frozenset()
            ),
        )

    @staticmethod
    def _selected_media(
        exercise: Exercise,
        profile_sex: Sex | None,
    ) -> tuple[str, str]:
        preferred_presentation = (
            MediaPresentation.MALE
            if profile_sex is Sex.MALE
            else MediaPresentation.FEMALE
            if profile_sex is Sex.FEMALE
            else None
        )
        assets = sorted(
            exercise.media_assets,
            key=lambda asset: (asset.presentation.value, asset.sort_order, str(asset.id)),
        )
        if preferred_presentation is not None:
            preferred_assets = [
                asset for asset in assets if asset.presentation is preferred_presentation
            ]
            fallback_assets = [
                asset for asset in assets if asset.presentation is not preferred_presentation
            ]
            selected = preferred_assets or fallback_assets
        else:
            selected = assets
        if selected:
            return selected[0].media_path, selected[0].media_type.value
        return exercise.media_path, exercise.media_type.value

    @staticmethod
    def _candidate_snapshot(candidate: ExerciseCandidate) -> dict[str, object]:
        return cast(dict[str, object], _json_ready(asdict(candidate)))

    @staticmethod
    def _catalog_hash(catalog: tuple[ExerciseCandidate, ...]) -> str:
        payload = [_json_ready(asdict(item)) for item in catalog]
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def _generation_signature(
        self,
        request: ProgramGenerationRequest,
        catalog_hash: str,
        reference_hash: str = "",
    ) -> str:
        return build_generation_request_signature(
            request,
            catalog_hash=catalog_hash,
            reference_hash=reference_hash,
            engine_version=self._ruleset.engine_version,
            ruleset_version=self._ruleset.version,
        )

    @staticmethod
    def _template_reference_hash(references: tuple[TemplateReference, ...]) -> str:
        payload = _json_ready([asdict(reference) for reference in references])
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _available_equipment(
        location: TrainingLocation,
        setup: HomeTrainingSetup | None,
    ) -> frozenset[Equipment]:
        if location is TrainingLocation.GYM:
            return frozenset(item for item in Equipment if item is not Equipment.OTHER)
        if setup is HomeTrainingSetup.DUMBBELLS_AVAILABLE:
            return frozenset({Equipment.BODYWEIGHT, Equipment.DUMBBELL})
        return frozenset({Equipment.BODYWEIGHT})

    def _mark_failure(
        self,
        generation: WorkoutPlanGeneration,
        error_code: str,
        safe_message: str,
        diagnostics: list[dict[str, object]],
    ) -> None:
        try:
            if generation not in self._db:
                generation = self._db.get(WorkoutPlanGeneration, generation.id) or generation
            fail_generation(
                self._db,
                generation,
                error_code=error_code,
                safe_error_message=safe_message,
                validation_diagnostics=diagnostics or None,
            )
            self._db.commit()
        except SQLAlchemyError:
            self._db.rollback()

    def get_active(self, user_id: UUID) -> ActiveWorkoutPlanResult | None:
        plan = get_active_plan(self._db, user_id)
        if plan is None:
            return None
        if self._settings.generation_method == "ai":
            profile = self._to_generation_profile(get_profile(self._db, user_id))
            eligible_exercises = WorkoutCandidateSelector(
                self._db, maximum_candidates=self._settings.max_candidates
            ).select(profile)
            candidates = select_ai_coach_candidates(
                templates=load_template_references(self._db),
                profile=profile,
                eligible_exercise_ids=frozenset(eligible_exercises.ids),
            )
            signature = self._ai_coach_generation_signature(profile, candidates, eligible_exercises)
            return ActiveWorkoutPlanResult(
                plan=plan,
                is_stale=plan.generation_signature != signature or self._is_plan_expired(plan),
            )
        request = self._to_program_request(
            get_profile(self._db, user_id),
            None,
            applicable_body_analysis_influence(
                self._body_analysis_resolver.resolve(user_id), self._ruleset
            ),
        )
        source_profile = get_profile(self._db, user_id)
        catalog_hash = self._catalog_hash(self._load_catalog(source_profile.profile.sex))
        reference_hash = self._template_reference_hash(load_template_references(self._db))
        is_stale = plan.generation_signature != self._generation_signature(
            request, catalog_hash, reference_hash
        ) or self._is_plan_expired(plan)
        return ActiveWorkoutPlanResult(plan=plan, is_stale=is_stale)

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

    @staticmethod
    def plan_duration_weeks(plan: WorkoutPlan) -> int:
        value = plan.profile_snapshot.get("program_duration_weeks")
        if not isinstance(value, int):
            value = plan.profile_snapshot.get("plan_duration_weeks")
        return value if isinstance(value, int) and 2 <= value <= 52 else 4

    @classmethod
    def _is_plan_expired(cls, plan: WorkoutPlan) -> bool:
        started_at = plan.activated_at or plan.created_at
        return datetime.now(UTC) >= started_at + timedelta(weeks=cls.plan_duration_weeks(plan))


def _generation_failure_messages(
    error_code: GenerationErrorCode | None,
) -> tuple[str, str]:
    if error_code is GenerationErrorCode.UNSUPPORTED_RESISTANCE_TRAINING_DAYS:
        return (
            "The requested resistance-training schedule is not supported "
            "for this experience level.",
            "The requested resistance-training day count is outside the official "
            "compatibility matrix.",
        )
    if error_code is GenerationErrorCode.UNSATISFIED_CONSTRAINT:
        return (
            "No safe workout layout satisfies all required session constraints.",
            "Safe program construction exhausted all ranked split alternatives.",
        )
    if error_code in {
        GenerationErrorCode.NO_SAFE_EXERCISE_FOR_PATTERN,
        GenerationErrorCode.NO_AVAILABLE_EQUIPMENT_MATCH,
        GenerationErrorCode.INSUFFICIENT_ELIGIBLE_EXERCISES,
    }:
        return (
            "A safe workout cannot be generated from the currently eligible exercises.",
            "No eligible exercise satisfies this required workout constraint.",
        )
    if error_code is GenerationErrorCode.PROGRAM_REJECTED_SAFETY_STATUS:
        return (
            "Professional review is required before automatic programming.",
            "The current safety status disallows automatic workout generation.",
        )
    return (
        "A safe valid workout program could not be generated.",
        "Deterministic program validation rejected this generation.",
    )


def _json_ready(value: object) -> object:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(_json_ready(key)): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        items = [_json_ready(item) for item in value]
        return sorted(
            items,
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        )
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    return value
