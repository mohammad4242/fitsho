from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.body_analysis.enums import BodyArea
from app.exercises.enums import MuscleGroup
from app.profile.enums import HomeTrainingSetup, TrainingLocation
from app.workout_cycles.enums import (
    WorkoutCycleWeeklyCheckInDifficulty,
    WorkoutCycleWeeklyCheckInRecovery,
)


class AthleteStateTrendDirection(StrEnum):
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    UNKNOWN = "unknown"


class AthleteStateAdherence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sessions_completed: int = Field(ge=0)
    planned_sessions: int = Field(ge=0)
    percent: float | None = Field(default=None, ge=0, le=100)
    source_check_in_ids: tuple[UUID, ...] = ()


class AthleteStateRecoveryTrend(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    latest: WorkoutCycleWeeklyCheckInRecovery | None = None
    values: tuple[WorkoutCycleWeeklyCheckInRecovery, ...] = ()
    direction: AthleteStateTrendDirection = AthleteStateTrendDirection.UNKNOWN
    source_check_in_ids: tuple[UUID, ...] = ()


class AthleteStateDifficultyTrend(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    latest: WorkoutCycleWeeklyCheckInDifficulty | None = None
    values: tuple[WorkoutCycleWeeklyCheckInDifficulty, ...] = ()
    direction: AthleteStateTrendDirection = AthleteStateTrendDirection.UNKNOWN
    source_check_in_ids: tuple[UUID, ...] = ()


class AthleteStateExerciseContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    exercise_id: UUID
    source_preference_ids: tuple[UUID, ...] = ()
    source_replacement_ids: tuple[UUID, ...] = ()


class AthleteStateScheduleContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    current_training_days_per_week: int | None = Field(default=None, ge=2, le=6)
    current_session_duration_minutes: int | None = Field(default=None, ge=30, le=120)
    next_training_days: int | None = Field(default=None, ge=2, le=6)
    next_session_duration_minutes: int | None = Field(default=None, ge=30, le=120)
    training_location: TrainingLocation | None = None
    home_training_setup: HomeTrainingSetup | None = None
    source_feedback_id: UUID | None = None
    source_profile_user_id: UUID | None = None


class AthleteStateBodyProgress(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    improved_areas: tuple[BodyArea, ...] = ()
    unchanged_areas: tuple[BodyArea, ...] = ()
    lagging_areas: tuple[BodyArea, ...] = ()
    comparison_ids: tuple[UUID, ...] = ()


class AthleteStateProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_user_id: UUID | None = None
    cycle_ids: tuple[UUID, ...] = ()
    weekly_check_in_ids: tuple[UUID, ...] = ()
    end_feedback_ids: tuple[UUID, ...] = ()
    replacement_ids: tuple[UUID, ...] = ()
    preference_ids: tuple[UUID, ...] = ()
    preference_source_replacement_ids: tuple[UUID, ...] = ()
    safety_signal_ids: tuple[UUID, ...] = ()
    body_progress_comparison_ids: tuple[UUID, ...] = ()
    body_measurement_ids: tuple[UUID, ...] = ()
    body_analysis_ids: tuple[UUID, ...] = ()
    workout_plan_ids: tuple[UUID, ...] = ()


class AthleteState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1.0"
    user_id: UUID
    current_cycle_id: UUID | None = None
    previous_cycle_ids: tuple[UUID, ...] = ()
    adherence: AthleteStateAdherence
    recovery_trend: AthleteStateRecoveryTrend
    difficulty_trend: AthleteStateDifficultyTrend
    persistent_disliked_exercises: tuple[UUID, ...] = ()
    uncomfortable_exercises: tuple[UUID, ...] = ()
    unavailable_exercises: tuple[UUID, ...] = ()
    unavailable_equipment_context: tuple[AthleteStateExerciseContext, ...] = ()
    pain_sensitive_exercises: tuple[UUID, ...] = ()
    priority_muscles: tuple[MuscleGroup, ...] = ()
    progressing_muscles: tuple[MuscleGroup, ...] = ()
    lagging_muscles: tuple[MuscleGroup, ...] = ()
    schedule: AthleteStateScheduleContext
    body_progress: AthleteStateBodyProgress
    provenance: AthleteStateProvenance
