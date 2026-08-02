from __future__ import annotations

from dataclasses import dataclass, field
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.exercises.enums import (
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseLabel,
    ExerciseType,
    MovementPattern,
    MuscleGroup,
)
from app.profile.enums import TrainingLocation
from app.workouts.program_engine.enums import (
    ActivityLevel,
    BalanceAbility,
    BodyPosition,
    CardioIntensity,
    GenerationErrorCode,
    Goal,
    ImpactLimit,
    Laterality,
    LoadLimit,
    MedicalClearanceStatus,
    PhysicalJobDemand,
    RecoveryRating,
    RedFlag,
    SafetyStatus,
    SkillDemand,
    SplitType,
    StabilityDemand,
    TrainingExperience,
    TrainingStatus,
)

GOAL_ALIASES: dict[str, Goal] = {
    "weight_loss": Goal.FAT_LOSS,
    "lose_weight": Goal.FAT_LOSS,
    "weight_gain": Goal.MUSCLE_GAIN,
    "build_muscle": Goal.MUSCLE_GAIN,
    "improve_fitness": Goal.GENERAL_FITNESS,
    "maintain_weight": Goal.GENERAL_FITNESS,
}


class Limitation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=2, max_length=160)
    stable: bool
    blocked_movement_patterns: frozenset[MovementPattern] = frozenset()
    blocked_caution_tags: frozenset[ExerciseCautionTag] = frozenset()
    allowed_range_of_motion: frozenset[str] = frozenset()
    impact_limit: ImpactLimit | None = None
    axial_load_limit: LoadLimit | None = None
    overhead_limit: LoadLimit | None = None
    balance_requirement: BalanceAbility | None = None

    @property
    def has_computable_constraint(self) -> bool:
        return bool(
            self.blocked_movement_patterns
            or self.blocked_caution_tags
            or self.allowed_range_of_motion
            or self.impact_limit
            or self.axial_load_limit
            or self.overhead_limit
            or self.balance_requirement
        )


class RecentTrainingHistory(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    consistent_weeks: int | None = Field(default=None, ge=0, le=520)
    completed_session_ratio: float = Field(default=0.0, ge=0, le=1)
    previous_weekly_sets_by_muscle: dict[MuscleGroup, int] = Field(default_factory=dict)
    performance_trend: str | None = None
    recovery_problems: bool = False


class ProgramGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    user_id: UUID
    age: Annotated[int, Field(ge=18, le=100)]
    biological_sex_optional: str | None = None
    height_cm: Annotated[int, Field(ge=100, le=250)]
    weight_kg: Annotated[float, Field(ge=30, le=400)]
    primary_goal: Goal
    secondary_goal_optional: Goal | None = None
    training_experience: TrainingExperience
    training_age_months: Annotated[int, Field(ge=0, le=900)]
    current_activity_level: ActivityLevel = ActivityLevel.MODERATE
    available_training_days: Annotated[int, Field(ge=1, le=7)]
    preferred_weekdays: tuple[int, ...] = ()
    session_duration_minutes: Annotated[int, Field(ge=20, le=180)]
    available_equipment: frozenset[Equipment]
    training_location: TrainingLocation
    preferred_exercises: frozenset[UUID] = frozenset()
    disliked_exercises: frozenset[UUID] = frozenset()
    priority_muscles: frozenset[MuscleGroup] = frozenset()
    injuries_and_limitations: tuple[Limitation, ...] = ()
    blocked_exercises: frozenset[UUID] = frozenset()
    blocked_movement_patterns: frozenset[MovementPattern] = frozenset()
    blocked_caution_tags: frozenset[ExerciseCautionTag] = frozenset()
    allowed_range_of_motion: frozenset[str] = frozenset()
    impact_limit: ImpactLimit = ImpactLimit.HIGH
    axial_load_limit: LoadLimit = LoadLimit.HIGH
    overhead_limit: LoadLimit = LoadLimit.HIGH
    balance_requirement: BalanceAbility = BalanceAbility.NORMAL
    current_pain_or_red_flags: tuple[RedFlag, ...] = ()
    medical_clearance_status: MedicalClearanceStatus = MedicalClearanceStatus.NOT_REQUIRED
    reports_uncontrolled_medical_condition: bool = False
    pregnancy_or_postpartum: bool = False
    sleep_quality: RecoveryRating = RecoveryRating.AVERAGE
    stress_level: RecoveryRating = RecoveryRating.AVERAGE
    physical_job_demand: PhysicalJobDemand = PhysicalJobDemand.LOW
    cardio_tolerance: ActivityLevel = ActivityLevel.MODERATE
    recent_training_history: RecentTrainingHistory = Field(default_factory=RecentTrainingHistory)
    known_strength_data: dict[UUID, float] = Field(default_factory=dict)
    program_duration_weeks: Annotated[int, Field(ge=2, le=52)] = 4
    seed_optional: int | None = None

    @field_validator("primary_goal", "secondary_goal_optional", mode="before")
    @classmethod
    def normalize_goal_alias(cls, value: object) -> object:
        if isinstance(value, str):
            return GOAL_ALIASES.get(value, value)
        return value

    @field_validator("preferred_weekdays")
    @classmethod
    def validate_weekdays(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if len(value) != len(set(value)) or any(day < 0 or day > 6 for day in value):
            raise ValueError("preferred weekdays must be unique values from 0 through 6")
        return value


@dataclass(frozen=True)
class DerivedConstraints:
    available_equipment: frozenset[Equipment]
    blocked_exercises: frozenset[UUID]
    blocked_movement_patterns: frozenset[MovementPattern]
    blocked_caution_tags: frozenset[ExerciseCautionTag]
    allowed_range_of_motion: frozenset[str]
    impact_limit: ImpactLimit
    axial_load_limit: LoadLimit
    overhead_limit: LoadLimit
    balance_requirement: BalanceAbility


@dataclass(frozen=True)
class NormalizedProgramRequest:
    source: ProgramGenerationRequest
    primary_goal: Goal
    training_status: TrainingStatus
    resistance_training_days: int
    seed: int
    constraints: DerivedConstraints
    assumptions: tuple[str, ...]


@dataclass(frozen=True)
class SafetyAssessment:
    status: SafetyStatus
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class ExerciseCandidate:
    id: UUID
    name: str
    primary_muscle: MuscleGroup | None
    secondary_muscles: tuple[MuscleGroup, ...]
    movement_pattern: MovementPattern
    exercise_type: ExerciseType
    equipment: frozenset[Equipment]
    difficulty: Difficulty
    caution_tags: frozenset[ExerciseCautionTag] = frozenset()
    labels: frozenset[ExerciseLabel] = frozenset()
    is_active: bool = True
    is_programmable: bool = True
    needs_review: bool = False
    laterality: Laterality = Laterality.BILATERAL
    body_position: BodyPosition = BodyPosition.STANDING
    stability_demand: StabilityDemand = StabilityDemand.MODERATE
    skill_demand: SkillDemand = SkillDemand.MODERATE
    impact_level: ImpactLimit = ImpactLimit.LOW
    axial_loading_level: LoadLimit = LoadLimit.LOW
    fatigue_cost: int = 2
    setup_cost: int = 1
    range_of_motion_profile: frozenset[str] = frozenset()
    substitution_group: str | None = None
    progression_exercise_ids: tuple[UUID, ...] = ()
    regression_exercise_ids: tuple[UUID, ...] = ()
    display_snapshot: dict[str, object] = field(default_factory=dict)

    @property
    def has_required_metadata(self) -> bool:
        if ExerciseLabel.CARDIO in self.labels:
            return bool(self.name and self.equipment)
        return self.primary_muscle is not None and self.movement_pattern.value != "other"


@dataclass(frozen=True)
class SplitCandidate:
    split_type: SplitType
    day_focuses: tuple[str, ...]


@dataclass(frozen=True)
class SplitPlan:
    split_type: SplitType
    day_focuses: tuple[str, ...]
    weekdays: tuple[int, ...]
    score: int
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class VolumeTarget:
    muscle: MuscleGroup
    minimum_soft: int
    target_sets: int
    maximum_soft: int
    maximum_hard: int
    fractional_sets: float

    @property
    def direct_sets(self) -> int:
        """Compatibility alias for the planned direct-set target."""
        return self.target_sets


@dataclass(frozen=True)
class WeeklyVolumePlan:
    targets: tuple[VolumeTarget, ...]
    reason_codes: tuple[str, ...]

    def direct_sets_for(self, muscle: MuscleGroup) -> int:
        return next((item.direct_sets for item in self.targets if item.muscle is muscle), 0)


@dataclass(frozen=True)
class RejectedCandidate:
    exercise_id: UUID
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class EligibilityResult:
    eligible: tuple[ExerciseCandidate, ...]
    rejected: tuple[RejectedCandidate, ...]


@dataclass(frozen=True)
class RankedCandidate:
    exercise: ExerciseCandidate
    score: int
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class ProgrammedExercise:
    exercise_id: UUID
    exercise_name: str
    order: int
    sets: int
    rep_min: int
    rep_max: int
    target_rir: int
    rest_seconds: int
    estimated_minutes: int
    reason_codes: tuple[str, ...]
    substitution_exercise_ids: tuple[UUID, ...] = ()
    warmup_sets: int = 0
    load_guidance: str = "Select a load that preserves the target RIR."
    notes: str | None = None
    progression_rule: str = "double_progression_v1"
    counts_toward_volume: bool = True
    movement_pattern: MovementPattern = MovementPattern.OTHER
    primary_muscle: MuscleGroup | None = None
    secondary_muscles: tuple[MuscleGroup, ...] = ()
    equipment: frozenset[Equipment] = frozenset()
    caution_tags: frozenset[ExerciseCautionTag] = frozenset()
    range_of_motion_profile: frozenset[str] = frozenset()
    impact_level: ImpactLimit = ImpactLimit.LOW
    axial_loading_level: LoadLimit = LoadLimit.LOW
    stability_demand: StabilityDemand = StabilityDemand.MODERATE
    is_active: bool = True
    is_programmable: bool = True
    needs_review: bool = False


@dataclass(frozen=True)
class CardioPrescription:
    modality_exercise_id: UUID
    modality_name: str
    duration_minutes: int
    intensity: CardioIntensity
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class WorkoutDay:
    day_index: int
    weekday: int | None
    title: str
    focus: str
    estimated_duration_minutes: int
    exercises: tuple[ProgrammedExercise, ...]
    cardio: CardioPrescription | None = None


@dataclass(frozen=True)
class ValidationReport:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    assumptions: tuple[str, ...]
    metrics: dict[str, object]
    decision_trace: tuple[dict[str, object], ...]

    @property
    def is_valid(self) -> bool:
        return not self.errors


@dataclass(frozen=True)
class WorkoutProgram:
    user_profile_snapshot: dict[str, object]
    engine_version: str
    ruleset_version: str
    seed: int
    primary_goal: Goal
    secondary_goal: Goal | None
    training_status: TrainingStatus
    safety_status: SafetyStatus
    assumptions: tuple[str, ...]
    warnings: tuple[str, ...]
    duration_weeks: int
    split: SplitPlan
    weekly_schedule: tuple[WorkoutDay, ...]
    progression_policy: dict[str, object]
    validation_report: ValidationReport
    aggregate_metrics: dict[str, object]
    decision_trace: tuple[dict[str, object], ...]


@dataclass(frozen=True)
class ProgramGenerationResult:
    program: WorkoutProgram | None
    error_code: GenerationErrorCode | None = None
    errors: tuple[str, ...] = ()
    safety_status: SafetyStatus | None = None
    rejected_candidates: tuple[RejectedCandidate, ...] = ()

    @property
    def is_success(self) -> bool:
        return self.program is not None and self.error_code is None


@dataclass
class SessionDraft:
    day_index: int
    weekday: int | None
    focus: str
    exercises: list[ExerciseCandidate] = field(default_factory=list)
    selection_reasons: dict[UUID, tuple[str, ...]] = field(default_factory=dict)
    substitutions: dict[UUID, tuple[UUID, ...]] = field(default_factory=dict)
    reason_codes: tuple[str, ...] = ()
