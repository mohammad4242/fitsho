from pydantic import BaseModel, ConfigDict, Field


class CompletionFeedbackInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    adherence_percent: int | None = Field(default=None, ge=0, le=100)
    performance_changes: str | None = Field(default=None, max_length=4000)
    pain_or_limitation_feedback: str | None = Field(default=None, max_length=4000)
    measurements: dict[str, int | float | str | None] = Field(default_factory=dict)
