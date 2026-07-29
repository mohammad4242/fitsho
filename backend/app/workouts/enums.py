from enum import StrEnum


class WorkoutPlanStatus(StrEnum):
    GENERATING = "generating"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    FAILED = "failed"


class WorkoutGenerationStatus(StrEnum):
    GENERATING = "generating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
