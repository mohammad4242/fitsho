from enum import StrEnum


class WorkoutCycleStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"


class WorkoutExerciseReplacementReason(StrEnum):
    EQUIPMENT_UNAVAILABLE = "equipment_unavailable"
    UNCOMFORTABLE = "uncomfortable"
    PAIN_OR_DISCOMFORT = "pain_or_discomfort"
    TEMPORARY_UNAVAILABLE = "temporary_unavailable"
    DISLIKE = "dislike"
    OTHER = "other"


class WorkoutExerciseReplacementScope(StrEnum):
    THIS_TIME = "this_time"
    PERSISTENT = "persistent"


class WorkoutExercisePreferenceType(StrEnum):
    EQUIPMENT_UNAVAILABLE = "equipment_unavailable"
    UNCOMFORTABLE = "uncomfortable"
    DISLIKE = "dislike"


class WorkoutExerciseSafetySignalType(StrEnum):
    PAIN_OR_DISCOMFORT = "pain_or_discomfort"


class WorkoutCycleWeeklyCheckInDifficulty(StrEnum):
    TOO_EASY = "too_easy"
    EASY = "easy"
    APPROPRIATE = "appropriate"
    HARD = "hard"
    TOO_HARD = "too_hard"


class WorkoutCycleWeeklyCheckInRecovery(StrEnum):
    GOOD = "good"
    AVERAGE = "average"
    POOR = "poor"
