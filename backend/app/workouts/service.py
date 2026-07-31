from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from math import ceil
from time import perf_counter
from typing import TYPE_CHECKING, cast
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.ai.schemas import ProviderErrorCode
from app.exercises.enums import (
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseType,
)
from app.exercises.models import Exercise
from app.profile.enums import ExperienceLevel, HomeTrainingSetup, TrainingLocation
from app.profile.service import ProfileSnapshot, get_profile
from app.workouts.candidate_selector import CAUTION_EXCLUSIONS
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.models import WorkoutDay, WorkoutPlan, WorkoutPlanExercise, WorkoutPlanGeneration
from app.workouts.program_engine.engine import generate_program
from app.workouts.program_engine.enums import (
    BodyPosition,
    GenerationErrorCode,
    ImpactLimit,
    LoadLimit,
    SkillDemand,
    StabilityDemand,
    TrainingExperience,
)
from app.workouts.program_engine.rulesets.resistance_training_v1 import RULESET, ProgramRuleset
from app.workouts.program_engine.schemas import (
    ExerciseCandidate,
    Limitation,
    ProgramGenerationRequest,
    WorkoutProgram,
)
from app.workouts.repository import (
    activate_plan,
    create_generation,
    fail_generation,
    get_active_plan,
    get_latest_completed_generation_at,
)
from app.workouts.schemas import ProgramGenerationOverrides
from app.workouts.signature import normalize_physical_limitations

if TYPE_CHECKING:
    from app.ai.routing import ModelProviderCandidate


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
    deterministic_fallback_enabled: bool = False


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


class GenerationInputsChangedError(Exception):
    pass


class WorkoutGenerationService:
    def __init__(
        self,
        db: Session,
        *,
        providers: tuple[ModelProviderCandidate, ...] = (),
        settings: WorkoutGenerationSettings,
        ruleset: ProgramRuleset = RULESET,
    ) -> None:
        self._db = db
        self._settings = settings
        self._ruleset = ruleset
        self._legacy_providers = providers

    async def generate(
        self,
        user_id: UUID,
        overrides: ProgramGenerationOverrides | None = None,
    ) -> WorkoutPlanGenerationResult:
        source_profile = get_profile(self._db, user_id)
        try:
            request = self._to_program_request(source_profile, overrides)
        except ValidationError as error:
            raise ProgramGenerationRejectedError("INVALID_PROFILE_INPUT") from error
        catalog = self._load_catalog()
        catalog_hash = self._catalog_hash(catalog)
        signature = self._generation_signature(request, catalog_hash)
        active_plan = get_active_plan(self._db, user_id)
        if (
            active_plan is not None
            and active_plan.generation_signature == signature
            and not self._is_plan_expired(active_plan)
        ):
            return WorkoutPlanGenerationResult(plan=active_plan, reused=True)

        self._enforce_cooldown(user_id)
        generation = self._start_generation(user_id, len(catalog))
        started_at = perf_counter()
        result = generate_program(request, catalog, self._ruleset)
        if not result.is_success or result.program is None:
            error_code = (
                result.error_code.value
                if result.error_code is not None
                else GenerationErrorCode.PROGRAM_VALIDATION_FAILED.value
            )
            self._mark_failure(
                generation,
                error_code,
                "A safe valid workout program could not be generated.",
                [{"errors": list(result.errors)}],
            )
            if result.error_code in {
                GenerationErrorCode.NO_SAFE_EXERCISE_FOR_PATTERN,
                GenerationErrorCode.NO_AVAILABLE_EQUIPMENT_MATCH,
                GenerationErrorCode.INSUFFICIENT_ELIGIBLE_EXERCISES,
                GenerationErrorCode.UNSATISFIED_CONSTRAINT,
            }:
                raise NoEligibleExercisesError(error_code)
            if result.error_code is GenerationErrorCode.PROGRAM_REJECTED_SAFETY_STATUS:
                raise ProgramGenerationRejectedError(
                    error_code,
                    result.safety_status.value if result.safety_status else None,
                )
            raise WorkoutGenerationFailedError(error_code=error_code)

        refreshed_profile = get_profile(self._db, user_id)
        refreshed_request = self._to_program_request(refreshed_profile, overrides)
        refreshed_catalog = self._load_catalog()
        if (
            self._generation_signature(refreshed_request, self._catalog_hash(refreshed_catalog))
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
            generation.provider = "fitsho_domain"
            generation.model_id = result.program.engine_version
            generation.latency_ms = int((perf_counter() - started_at) * 1000)
            generation.validation_diagnostics = [
                cast(dict[str, object], _json_ready(asdict(result.program.validation_report)))
            ]
            activate_plan(self._db, plan, generation)
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

    def _start_generation(self, user_id: UUID, candidate_count: int) -> WorkoutPlanGeneration:
        try:
            generation = create_generation(
                self._db,
                user_id=user_id,
                provider="fitsho_domain",
                model_id=self._ruleset.engine_version,
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
                title_fa=_persian_title(output_day.focus, output_day.day_index),
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
                        reps_min=item.rep_min,
                        reps_max=item.rep_max,
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
    ) -> ProgramGenerationRequest:
        profile = source.profile
        equipment = self._available_equipment(
            profile.training_location,
            profile.home_training_setup,
        )
        cautions = tuple(item.caution for item in profile.training_caution_items)
        blocked_caution_tags = set().union(*(CAUTION_EXCLUSIONS[item] for item in cautions))
        sanitized = self._sanitize_limitations(profile.physical_limitations)
        limitations = (Limitation(name=sanitized, stable=False),) if sanitized is not None else ()
        training_age = {
            ExperienceLevel.BEGINNER: 0,
            ExperienceLevel.INTERMEDIATE: 12,
            ExperienceLevel.ADVANCED: 48,
        }[profile.experience_level]
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
            "session_duration_minutes": profile.session_duration_minutes,
            "available_equipment": equipment,
            "training_location": profile.training_location,
            "injuries_and_limitations": limitations,
            "blocked_caution_tags": blocked_caution_tags,
            "program_duration_weeks": profile.plan_duration_weeks,
        }
        if overrides is not None:
            values.update(overrides.model_dump(exclude_none=True))
            values["user_id"] = profile.user_id
        return ProgramGenerationRequest.model_validate(values)

    def _load_catalog(self) -> tuple[ExerciseCandidate, ...]:
        exercises = self._db.scalars(
            select(Exercise).options(
                selectinload(Exercise.secondary_muscles),
                selectinload(Exercise.equipment_items),
                selectinload(Exercise.caution_tag_items),
                selectinload(Exercise.labels),
            )
        ).all()
        return tuple(
            sorted(
                (self._domain_candidate(item) for item in exercises),
                key=lambda item: str(item.id),
            )
        )

    @staticmethod
    def _domain_candidate(exercise: Exercise) -> ExerciseCandidate:
        caution_tags = frozenset(item.caution_tag for item in exercise.caution_tag_items)
        balance_demand = (
            StabilityDemand.HIGH
            if ExerciseCautionTag.BALANCE_DEMAND in caution_tags
            else StabilityDemand.LOW
            if exercise.exercise_type in {ExerciseType.ISOLATION, ExerciseType.CORE}
            else StabilityDemand.MODERATE
        )
        return ExerciseCandidate(
            id=exercise.id,
            name=exercise.name_en,
            primary_muscle=exercise.primary_muscle,
            secondary_muscles=tuple(item.muscle for item in exercise.secondary_muscles),
            movement_pattern=exercise.movement_pattern,
            exercise_type=exercise.exercise_type,
            equipment=frozenset(item.equipment for item in exercise.equipment_items),
            difficulty=exercise.difficulty,
            caution_tags=caution_tags,
            labels=frozenset(item.label for item in exercise.labels),
            is_active=exercise.is_active,
            is_programmable=exercise.is_programmable,
            needs_review=exercise.needs_review,
            body_position=BodyPosition.STANDING,
            stability_demand=balance_demand,
            skill_demand={
                Difficulty.BEGINNER: SkillDemand.LOW,
                Difficulty.INTERMEDIATE: SkillDemand.MODERATE,
                Difficulty.ADVANCED: SkillDemand.HIGH,
            }[exercise.difficulty],
            impact_level=ImpactLimit.LOW,
            axial_loading_level=(
                LoadLimit.HIGH
                if ExerciseCautionTag.LOWER_BACK_LOADING in caution_tags
                else LoadLimit.LOW
            ),
            fatigue_cost=3 if exercise.exercise_type is ExerciseType.COMPOUND else 1,
            setup_cost=1,
            range_of_motion_profile=(
                frozenset({"deep_knee_flexion"})
                if ExerciseCautionTag.DEEP_KNEE_FLEXION in caution_tags
                else frozenset()
            ),
            substitution_group=exercise.movement_pattern.value,
            display_snapshot={
                "id": str(exercise.id),
                "slug": exercise.slug,
                "name_en": exercise.name_en,
                "name_fa": exercise.name_fa,
                "body_region": exercise.body_region.value if exercise.body_region else None,
                "primary_muscle": (
                    exercise.primary_muscle.value if exercise.primary_muscle else None
                ),
                "labels": [item.label.value for item in exercise.labels],
                "secondary_muscles": [item.muscle.value for item in exercise.secondary_muscles],
                "equipment": [item.equipment.value for item in exercise.equipment_items],
                "difficulty": exercise.difficulty.value,
                "media_path": exercise.media_path,
                "media_type": exercise.media_type.value,
            },
        )

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
    ) -> str:
        payload = {
            "request": request.model_dump(mode="json"),
            "catalog_hash": catalog_hash,
            "engine_version": self._ruleset.engine_version,
            "ruleset_version": self._ruleset.version,
        }
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
        request = self._to_program_request(get_profile(self._db, user_id), None)
        catalog_hash = self._catalog_hash(self._load_catalog())
        is_stale = plan.generation_signature != self._generation_signature(
            request, catalog_hash
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


def _persian_title(focus: str, day_index: int) -> str:
    labels = {
        "upper": "بالاتنه",
        "lower": "پایین‌تنه",
        "push": "حرکات فشاری",
        "pull": "حرکات کششی",
        "legs": "پا",
        "specialization": "تخصصی",
    }
    label = labels.get(focus, "تمام بدن")
    return f"روز {day_index}: {label}"


def _json_ready(value: object) -> object:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(_json_ready(key)): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_ready(item) for item in value]
    return value
