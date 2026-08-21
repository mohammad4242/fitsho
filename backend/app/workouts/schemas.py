from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.exercises.enums import (
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseLabel,
    ExerciseType,
    MovementPattern,
    MuscleGroup,
    PrescriptionMode,
)
from app.exercises.schemas import ExerciseSummary
from app.profile.enums import (
    ExperienceLevel,
    FitnessGoal,
    HomeTrainingSetup,
    Sex,
    TrainingCaution,
    TrainingLocation,
)
from app.workouts.enums import WorkoutPlanStatus
from app.workouts.program_engine.enums import (
    ActivityLevel,
    BalanceAbility,
    Goal,
    ImpactLimit,
    LoadLimit,
    MedicalClearanceStatus,
    PhysicalJobDemand,
    RecoveryRating,
    RedFlag,
)
from app.workouts.program_engine.schemas import Limitation, RecentTrainingHistory


@dataclass(frozen=True)
class WorkoutGenerationProfile:
    fitness_goal: FitnessGoal | str
    experience_level: ExperienceLevel
    training_days_per_week: int
    training_location: TrainingLocation
    home_training_setup: HomeTrainingSetup | None
    session_duration_minutes: int
    plan_duration_weeks: int
    training_cautions: tuple[TrainingCaution, ...]
    physical_limitations: str | None
    current_weight_kg: Decimal | float | int | None
    age: int | None = None
    sex: Sex | None = None
    height_cm: int | None = None


@dataclass(frozen=True)
class WorkoutExerciseCandidate:
    id: UUID
    primary_muscle: MuscleGroup | None
    secondary_muscles: tuple[MuscleGroup, ...]
    movement_pattern: MovementPattern
    exercise_type: ExerciseType
    equipment: tuple[Equipment, ...]
    difficulty: Difficulty
    caution_tags: tuple[ExerciseCautionTag, ...]
    labels: tuple[ExerciseLabel, ...] = ()
    prescription_mode: PrescriptionMode = PrescriptionMode.REPS
    duration_min_seconds: int | None = None
    duration_max_seconds: int | None = None


@dataclass(frozen=True)
class CandidateSet:
    exercises: tuple[WorkoutExerciseCandidate, ...]
    candidate_set_hash: str
    soft_cautions: tuple[TrainingCaution, ...]
    minimum_candidate_count: int
    minimum_movement_pattern_count: int = 1

    @property
    def ids(self) -> tuple[UUID, ...]:
        return tuple(candidate.id for candidate in self.exercises)

    @property
    def is_sufficient(self) -> bool:
        return (
            len(self.exercises) >= self.minimum_candidate_count
            and len({item.movement_pattern for item in self.exercises})
            >= self.minimum_movement_pattern_count
        )


@dataclass(frozen=True)
class GenerationSignatureContext:
    fitness_goal: FitnessGoal | str
    experience_level: ExperienceLevel
    training_days_per_week: int
    training_location: TrainingLocation
    home_training_setup: HomeTrainingSetup | None
    session_duration_minutes: int
    plan_duration_weeks: int
    training_cautions: tuple[TrainingCaution, ...]
    physical_limitations: str | None
    current_weight_kg: Decimal | float | int | None
    candidate_set_hash: str
    catalog_programming_version: str
    model_id: str
    prompt_version: str
    generation_policy_version: str
    sex: Sex | None = None
    display_name: str | None = None
    age: int | None = None
    height_cm: int | None = None


class WorkoutPlanExerciseAlternativeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_en: str
    reason_fa: str
    exercise: ExerciseSummary


class WorkoutPlanExerciseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    order_index: int
    sets: int
    prescription_mode: PrescriptionMode = PrescriptionMode.REPS
    reps_min: int | None
    reps_max: int | None
    duration_min_seconds: int | None = None
    duration_max_seconds: int | None = None
    rest_seconds: int
    rir: int | None
    estimated_minutes: int
    notes_en: str | None
    notes_fa: str | None
    exercise: ExerciseSummary
    alternatives: list[WorkoutPlanExerciseAlternativeResponse]
    reason_codes: list[str] = Field(default_factory=list)
    warmup_sets: int = 0
    load_guidance: str = ""
    progression_rule: str = "legacy"

    @model_validator(mode="after")
    def validate_prescription(self) -> WorkoutPlanExerciseResponse:
        if self.prescription_mode is PrescriptionMode.REPS:
            if (
                self.reps_min is None
                or self.reps_max is None
                or not 1 <= self.reps_min <= self.reps_max <= 100
                or self.duration_min_seconds is not None
                or self.duration_max_seconds is not None
                or self.rir is None
            ):
                raise ValueError("rep prescriptions require reps, no duration, and RIR")
        elif self.prescription_mode is PrescriptionMode.DURATION:
            if (
                self.duration_min_seconds is None
                or self.duration_max_seconds is None
                or not 1 <= self.duration_min_seconds <= self.duration_max_seconds <= 3600
                or self.reps_min is not None
                or self.reps_max is not None
                or self.rir is not None
            ):
                raise ValueError("duration prescriptions require duration, no reps, and null RIR")
        else:
            raise ValueError(f"unsupported prescription mode: {self.prescription_mode}")
        return self


class WorkoutDayResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_number: int
    title_en: str
    title_fa: str
    estimated_duration_minutes: int
    exercises: list[WorkoutPlanExerciseResponse]
    weekday: int | None = None
    focus: str = "legacy"
    cardio: dict[str, object] | None = None
    ai_coach_explanation_fa: str | None = None


class WorkoutPlanCoachReviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Literal[
        "pending_coach_review",
        "initial_generated",
        "coach_approved",
        "none",
    ]
    coach_display_name: str | None = None
    coach_note: str | None = None
    approved_at: datetime | None = None


class WorkoutPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    status: WorkoutPlanStatus
    created_at: datetime
    activated_at: datetime | None
    plan_duration_weeks: int
    is_stale: bool
    days: list[WorkoutDayResponse]
    engine_version: str = "legacy_ai"
    ruleset_version: str = "legacy"
    seed: int = 0
    primary_goal: str = "general_fitness"
    secondary_goal: str | None = None
    training_status: str = "novice"
    safety_status: str = "clear"
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    validation_report: dict[str, object] = Field(default_factory=dict)
    aggregate_metrics: dict[str, object] = Field(default_factory=dict)
    progression_policy: dict[str, object] = Field(default_factory=dict)
    decision_trace: list[dict[str, object]] = Field(default_factory=list)
    body_analysis_provenance: dict[str, object] = Field(default_factory=dict)
    ai_coach_template_slug: str | None = None
    ai_coach_program_explanation_fa: str | None = None
    coach_review: WorkoutPlanCoachReviewResponse = Field(
        default_factory=lambda: WorkoutPlanCoachReviewResponse(state="none")
    )


class WorkoutPlanVersionSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    status: WorkoutPlanStatus
    created_at: datetime
    activated_at: datetime | None
    is_active: bool
    coach_review: WorkoutPlanCoachReviewResponse


class WorkoutPlanGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: WorkoutPlanResponse
    reused: bool


class ProgramGenerationOverrides(BaseModel):
    """Optional request-time evidence not yet stored in the core profile."""

    model_config = ConfigDict(extra="forbid")

    secondary_goal_optional: Goal | None = None
    available_training_days: int | None = Field(default=None, ge=1, le=7)
    session_duration_minutes: int | None = Field(default=None, ge=20, le=180)
    training_age_months: int | None = Field(default=None, ge=0, le=900)
    current_activity_level: ActivityLevel | None = None
    preferred_weekdays: tuple[int, ...] | None = None
    available_equipment: frozenset[Equipment] | None = None
    preferred_exercises: frozenset[UUID] = frozenset()
    disliked_exercises: frozenset[UUID] = frozenset()
    priority_muscles: frozenset[MuscleGroup] = frozenset()
    injuries_and_limitations: tuple[Limitation, ...] = ()
    blocked_exercises: frozenset[UUID] = frozenset()
    blocked_movement_patterns: frozenset[MovementPattern] = frozenset()
    blocked_caution_tags: frozenset[ExerciseCautionTag] = frozenset()
    allowed_range_of_motion: frozenset[str] = frozenset()
    impact_limit: ImpactLimit | None = None
    axial_load_limit: LoadLimit | None = None
    overhead_limit: LoadLimit | None = None
    balance_requirement: BalanceAbility | None = None
    current_pain_or_red_flags: tuple[RedFlag, ...] = ()
    medical_clearance_status: MedicalClearanceStatus | None = None
    reports_uncontrolled_medical_condition: bool = False
    pregnancy_or_postpartum: bool = False
    sleep_quality: RecoveryRating | None = None
    stress_level: RecoveryRating | None = None
    physical_job_demand: PhysicalJobDemand | None = None
    cardio_tolerance: ActivityLevel | None = None
    recent_training_history: RecentTrainingHistory | None = None
    known_strength_data: dict[UUID, float] = Field(default_factory=dict)
    seed_optional: int | None = None
