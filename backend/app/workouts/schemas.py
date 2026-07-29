from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.exercises.enums import (
    Difficulty,
    Equipment,
    ExerciseCautionTag,
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
    primary_muscle: MuscleGroup
    secondary_muscles: tuple[MuscleGroup, ...]
    movement_pattern: MovementPattern
    exercise_type: ExerciseType
    equipment: tuple[Equipment, ...]
    difficulty: Difficulty
    caution_tags: tuple[ExerciseCautionTag, ...]


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


class WorkoutDayResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_number: int
    title_en: str
    title_fa: str
    estimated_duration_minutes: int
    exercises: list[WorkoutPlanExerciseResponse]


class WorkoutPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    status: WorkoutPlanStatus
    created_at: datetime
    activated_at: datetime | None
    plan_duration_weeks: int
    is_stale: bool
    days: list[WorkoutDayResponse]


class WorkoutPlanGenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: WorkoutPlanResponse
    reused: bool
