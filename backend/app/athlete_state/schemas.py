from __future__ import annotations

import json
from enum import StrEnum
from typing import Any
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


class AthleteStateRecoverySummary(StrEnum):
    GOOD = "good"
    MIXED = "mixed"
    POOR = "poor"
    UNKNOWN = "unknown"


class AthleteStateDifficultySummary(StrEnum):
    TOO_EASY = "too_easy"
    APPROPRIATE = "appropriate"
    TOO_HARD = "too_hard"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class AthleteStateReasonCode(StrEnum):
    ADHERENCE_CALCULATED_FROM_WEEKLY_CHECK_INS = "adherence_calculated_from_weekly_check_ins"
    NO_WEEKLY_CHECK_IN_DATA = "no_weekly_check_in_data"
    ALL_RECENT_RECOVERY_GOOD = "all_recent_recovery_good"
    ALL_RECENT_RECOVERY_POOR = "all_recent_recovery_poor"
    MIXED_RECENT_RECOVERY = "mixed_recent_recovery"
    NO_RECOVERY_DATA = "no_recovery_data"
    CONSISTENTLY_TOO_EASY = "consistently_too_easy"
    CONSISTENTLY_APPROPRIATE = "consistently_appropriate"
    CONSISTENTLY_TOO_HARD = "consistently_too_hard"
    MIXED_RECENT_DIFFICULTY = "mixed_recent_difficulty"
    NO_DIFFICULTY_DATA = "no_difficulty_data"
    PERSISTENT_EQUIPMENT_CONTEXT = "persistent_equipment_context"
    LATEST_CONFIRMED_FEEDBACK_SCHEDULE = "latest_confirmed_feedback_schedule"
    PROFILE_SCHEDULE_FALLBACK = "profile_schedule_fallback"
    NO_SCHEDULE_DATA = "no_schedule_data"
    BODY_COMPARISON_EVIDENCE = "body_comparison_evidence"
    NO_BODY_PROGRESS_DATA = "no_body_progress_data"


class AthleteStateAdherence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    sessions_completed: int = Field(ge=0)
    planned_sessions: int = Field(ge=0)
    percent: float | None = Field(default=None, ge=0, le=100)
    source_check_in_ids: tuple[UUID, ...] = ()
    reason_codes: tuple[AthleteStateReasonCode, ...] = ()


class AthleteStateRecoveryTrend(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    latest: WorkoutCycleWeeklyCheckInRecovery | None = None
    values: tuple[WorkoutCycleWeeklyCheckInRecovery, ...] = ()
    direction: AthleteStateTrendDirection = AthleteStateTrendDirection.UNKNOWN
    source_check_in_ids: tuple[UUID, ...] = ()
    summary: AthleteStateRecoverySummary = AthleteStateRecoverySummary.UNKNOWN
    reason_codes: tuple[AthleteStateReasonCode, ...] = ()


class AthleteStateDifficultyTrend(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    latest: WorkoutCycleWeeklyCheckInDifficulty | None = None
    values: tuple[WorkoutCycleWeeklyCheckInDifficulty, ...] = ()
    direction: AthleteStateTrendDirection = AthleteStateTrendDirection.UNKNOWN
    source_check_in_ids: tuple[UUID, ...] = ()
    summary: AthleteStateDifficultySummary = AthleteStateDifficultySummary.UNKNOWN
    reason_codes: tuple[AthleteStateReasonCode, ...] = ()


class AthleteStateExerciseContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    exercise_id: UUID
    source_preference_ids: tuple[UUID, ...] = ()
    source_replacement_ids: tuple[UUID, ...] = ()
    reason_codes: tuple[AthleteStateReasonCode, ...] = ()


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
    reason_codes: tuple[AthleteStateReasonCode, ...] = ()


class AthleteStateBodyProgress(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    improved_areas: tuple[BodyArea, ...] = ()
    unchanged_areas: tuple[BodyArea, ...] = ()
    lagging_areas: tuple[BodyArea, ...] = ()
    comparison_ids: tuple[UUID, ...] = ()
    reason_codes: tuple[AthleteStateReasonCode, ...] = ()


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

    def to_snapshot(self) -> dict[str, Any]:
        """Return the public, JSON-compatible state without raw source records."""
        return self.model_dump(mode="json")

    def to_snapshot_json(self) -> str:
        """Return a canonical JSON representation suitable for hashing or tracing."""
        return json.dumps(
            self.to_snapshot(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
