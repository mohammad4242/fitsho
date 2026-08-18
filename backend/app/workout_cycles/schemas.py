from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.workout_cycles.enums import (
    WorkoutCycleStatus,
    WorkoutCycleWeeklyCheckInDifficulty,
    WorkoutCycleWeeklyCheckInRecovery,
    WorkoutExerciseReplacementReason,
    WorkoutExerciseReplacementScope,
)


class WorkoutCycleWeeklyCheckInClassificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    perceived_difficulty: WorkoutCycleWeeklyCheckInDifficulty
    recovery_rating: WorkoutCycleWeeklyCheckInRecovery


class WorkoutExerciseReplacementCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workout_plan_exercise_id: UUID
    replacement_exercise_id: UUID
    reason: WorkoutExerciseReplacementReason
    scope: WorkoutExerciseReplacementScope


class WorkoutExerciseReplacementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    user_id: UUID
    cycle_id: UUID
    workout_plan_exercise_id: UUID
    original_exercise_id: UUID
    replacement_exercise_id: UUID
    reason: WorkoutExerciseReplacementReason
    scope: WorkoutExerciseReplacementScope
    week_number: int
    created_at: datetime


class WorkoutCycleCurrentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cycle_id: UUID
    workout_plan_id: UUID
    started_at: datetime
    duration_weeks: int
    status: WorkoutCycleStatus
    current_week: int


class CompletionFeedbackInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adherence_percent: int | None = Field(default=None, ge=0, le=100)
    performance_changes: str | None = Field(default=None, max_length=4000)
    pain_or_limitation_feedback: str | None = Field(default=None, max_length=4000)
    measurements: dict[str, int | float | str | None] = Field(default_factory=dict)
