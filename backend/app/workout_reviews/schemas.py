from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.athlete_state.schemas import AthleteState
from app.exercises.enums import PrescriptionMode
from app.workout_reviews.enums import WorkoutReviewStatus
from app.workouts.program_engine.adaptation_policy import CycleAdaptationDecision
from app.workouts.program_engine.enums import ValidationStatus


class WorkoutReviewExerciseDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_index: int = Field(ge=1)
    exercise_id: UUID
    sets: int = Field(ge=1, le=10)
    prescription_mode: PrescriptionMode = PrescriptionMode.REPS
    reps_min: int | None = Field(default=None, ge=1, le=100)
    reps_max: int | None = Field(default=None, ge=1, le=100)
    duration_min_seconds: int | None = Field(default=None, ge=1, le=3600)
    duration_max_seconds: int | None = Field(default=None, ge=1, le=3600)
    rir: int | None = Field(default=None, ge=0, le=5)
    rest_seconds: int = Field(ge=0, le=600)
    notes_en: str | None = Field(default=None, max_length=1000)
    notes_fa: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_repetition_range(self) -> WorkoutReviewExerciseDraft:
        if self.prescription_mode is PrescriptionMode.REPS:
            if (
                self.reps_min is None
                or self.reps_max is None
                or self.reps_min > self.reps_max
                or self.duration_min_seconds is not None
                or self.duration_max_seconds is not None
            ):
                raise ValueError("rep prescriptions require reps, no duration, and RIR")
        elif self.prescription_mode is PrescriptionMode.DURATION:
            if (
                self.duration_min_seconds is None
                or self.duration_max_seconds is None
                or self.duration_min_seconds > self.duration_max_seconds
                or self.reps_min is not None
                or self.reps_max is not None
                or self.rir is not None
            ):
                raise ValueError("duration prescriptions require duration, no reps, and null RIR")
        else:
            raise ValueError(f"unsupported prescription mode: {self.prescription_mode}")
        return self


class WorkoutReviewDayDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_number: int = Field(ge=1, le=6)
    exercises: list[WorkoutReviewExerciseDraft] = Field(min_length=1, max_length=10)


class WorkoutReviewDraftUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)
    coach_note: str | None = Field(default=None, max_length=2000)
    days: list[WorkoutReviewDayDraft] = Field(min_length=1, max_length=6)


class WorkoutReviewApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)


class WorkoutReviewExerciseOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    name_en: str
    name_fa: str
    prescription_mode: PrescriptionMode = PrescriptionMode.REPS
    duration_min_seconds: int | None = None
    duration_max_seconds: int | None = None


class WorkoutReviewAthleteSummary(BaseModel):
    """Compact, derived athlete context for the coach review surface."""

    model_config = ConfigDict(extra="forbid")

    athlete_state: AthleteState
    previous_approved_plan_id: UUID | None = None


class CoachTemplateSelectionScoreResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: int
    body_analysis: int
    goal: int
    sex: int
    fallback: int
    total: int


class CoachTemplateSelectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_template: str
    explanation_fa: str
    explanation_en: str
    score: CoachTemplateSelectionScoreResponse


class CoachQualityRatioResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    satisfied: float = Field(ge=0)
    total: float = Field(ge=0)
    percentage: float | None = Field(default=None, ge=0, le=100)


class CoachQualityMetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_preservation: CoachQualityRatioResponse
    priority_target_satisfaction: CoachQualityRatioResponse
    body_analysis_target_satisfaction: CoachQualityRatioResponse
    volume_fit: CoachQualityRatioResponse
    duration_fit: CoachQualityRatioResponse
    recovery_fit: CoachQualityRatioResponse
    substitution_count: int = Field(ge=0)
    constraint_count: int = Field(ge=0)
    hard_validation_status: ValidationStatus


class WorkoutReviewQueueItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    source_plan_id: UUID
    user_id: UUID
    member_display_name: str | None
    fitness_goal: str | None
    experience_level: str | None
    status: WorkoutReviewStatus
    claimed_by_user_id: UUID | None
    lease_expires_at: datetime | None
    draft_revision: int
    created_at: datetime
    approved_at: datetime | None


class WorkoutReviewDetailResponse(WorkoutReviewQueueItemResponse):
    coach_note: str | None
    draft: dict[str, object] | None
    source_plan: dict[str, object]
    exercise_options: list[WorkoutReviewExerciseOption]
    athlete_summary: WorkoutReviewAthleteSummary
    fitsho_recommendation: CycleAdaptationDecision
    template_selection: CoachTemplateSelectionResponse | None = None
    coach_quality_metrics: CoachQualityMetricsResponse | None = None


class WorkoutReviewAccessResponse(BaseModel):
    authorized: Literal[True] = True
