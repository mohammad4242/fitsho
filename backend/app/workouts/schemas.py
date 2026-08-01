from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.exercises.enums import (
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseLabel,
    ExerciseType,
    MovementPattern,
    MuscleGroup,
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

    order_index: int
    sets: int
    reps_min: int
    reps_max: int
    rest_seconds: int
    rir: int
    estimated_minutes: int
    notes_en: str | None
    notes_fa: str | None
    exercise: ExerciseSummary
    alternatives: list[WorkoutPlanExerciseAlternativeResponse]
    reason_codes: list[str] = Field(default_factory=list)
    warmup_sets: int = 0
    load_guidance: str = ""
    progression_rule: str = "legacy"


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


class WorkoutPlanGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: WorkoutPlanResponse
    reused: bool


class ProgramGenerationOverrides(BaseModel):
    """Optional request-time evidence not yet stored in the core profile."""

    model_config = ConfigDict(extra="forbid")

    secondary_goal_optional: Goal | None = None
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
