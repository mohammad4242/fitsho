from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.exercises.enums import MuscleGroup
from app.profile.schemas import SessionDurationMinutes
from app.workout_cycles.enums import (
    WorkoutCycleFeedbackProgress,
    WorkoutCycleFeedbackSatisfaction,
    WorkoutCycleStatus,
    WorkoutCycleWeeklyCheckInDifficulty,
    WorkoutCycleWeeklyCheckInRecovery,
    WorkoutExerciseReplacementReason,
    WorkoutExerciseReplacementScope,
)
from app.workouts.program_engine.enums import Goal


class WorkoutCycleWeeklyCheckInClassificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    perceived_difficulty: WorkoutCycleWeeklyCheckInDifficulty
    recovery_rating: WorkoutCycleWeeklyCheckInRecovery


class WorkoutCycleWeeklyCheckInPainFollowUpInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workout_plan_exercise_id: UUID
    note_optional: str | None = Field(default=None, max_length=500)


class WorkoutCycleWeeklyCheckInUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sessions_completed: int = Field(ge=0)
    perceived_difficulty: WorkoutCycleWeeklyCheckInDifficulty
    recovery_rating: WorkoutCycleWeeklyCheckInRecovery
    has_pain_or_limitation: bool
    pain_follow_up: WorkoutCycleWeeklyCheckInPainFollowUpInput | None = None
    note_optional: str | None = Field(default=None, max_length=2000)


class WorkoutCycleWeeklyCheckInPainFollowUpResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    workout_plan_exercise_id: UUID
    note_optional: str | None
    created_at: datetime


class WorkoutCycleWeeklyCheckInResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    user_id: UUID
    cycle_id: UUID
    week_number: int
    sessions_completed: int
    perceived_difficulty: WorkoutCycleWeeklyCheckInDifficulty
    recovery_rating: WorkoutCycleWeeklyCheckInRecovery
    has_pain_or_limitation: bool
    pain_follow_up: WorkoutCycleWeeklyCheckInPainFollowUpResponse | None
    note_optional: str | None
    submitted_at: datetime
    created_at: datetime
    updated_at: datetime


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
    overall_difficulty: WorkoutCycleWeeklyCheckInDifficulty | None = None
    overall_recovery: WorkoutCycleWeeklyCheckInRecovery | None = None
    overall_satisfaction: WorkoutCycleFeedbackSatisfaction | None = None
    strength_progress: WorkoutCycleFeedbackProgress | None = None
    muscle_progress: WorkoutCycleFeedbackProgress | None = None
    endurance_progress: WorkoutCycleFeedbackProgress | None = None
    energy_progress: WorkoutCycleFeedbackProgress | None = None
    progressed_muscles: list[MuscleGroup] | None = None
    lagging_muscles: list[MuscleGroup] | None = None
    goal_changed: bool | None = None
    next_goal: Goal | None = None
    schedule_changed: bool | None = None
    next_training_days: int | None = Field(default=None, ge=2, le=6)
    next_session_duration_minutes: SessionDurationMinutes | None = None
    equipment_changed: bool | None = None
    new_limitation: str | None = Field(default=None, max_length=1000)
    note_optional: str | None = Field(default=None, max_length=4000)
