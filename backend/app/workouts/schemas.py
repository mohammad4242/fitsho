from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.exercises.enums import (
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseType,
    MovementPattern,
    MuscleGroup,
)
from app.profile.enums import (
    ExperienceLevel,
    FitnessGoal,
    HomeTrainingSetup,
    Sex,
    TrainingCaution,
    TrainingLocation,
)


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

    @property
    def ids(self) -> tuple[UUID, ...]:
        return tuple(candidate.id for candidate in self.exercises)

    @property
    def is_sufficient(self) -> bool:
        return len(self.exercises) >= self.minimum_candidate_count


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
    display_name: str | None = None
    age: int | None = None
    height_cm: int | None = None
