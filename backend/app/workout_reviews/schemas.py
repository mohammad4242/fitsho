from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WorkoutReviewExerciseDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_index: int = Field(ge=1)
    exercise_id: UUID
    sets: int = Field(ge=1, le=10)
    reps_min: int = Field(ge=1, le=100)
    reps_max: int = Field(ge=1, le=100)
    rest_seconds: int = Field(ge=0, le=600)
    notes_en: str | None = Field(default=None, max_length=1000)
    notes_fa: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_repetition_range(self) -> WorkoutReviewExerciseDraft:
        if self.reps_min > self.reps_max:
            raise ValueError("reps_min must not exceed reps_max")
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
