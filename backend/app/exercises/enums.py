from enum import StrEnum


class BodyRegion(StrEnum):
    UPPER_BODY = "upper_body"
    LOWER_BODY = "lower_body"
    CORE = "core"


class MuscleGroup(StrEnum):
    CHEST = "chest"
    BACK = "back"
    SHOULDERS = "shoulders"
    BICEPS = "biceps"
    TRICEPS = "triceps"
    TRAPS = "traps"
    GLUTES = "glutes"
    QUADRICEPS = "quadriceps"
    HAMSTRINGS = "hamstrings"
    ADDUCTORS = "adductors"
    CALVES = "calves"
    ABS = "abs"
    OBLIQUES = "obliques"
    LOWER_BACK = "lower_back"


class Equipment(StrEnum):
    BODYWEIGHT = "bodyweight"
    DUMBBELL = "dumbbell"
    BARBELL = "barbell"
    CABLE = "cable"
    MACHINE = "machine"
    RESISTANCE_BAND = "resistance_band"
    BENCH = "bench"
    PULL_UP_BAR = "pull_up_bar"
    OTHER = "other"


class Difficulty(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class MediaType(StrEnum):
    IMAGE = "image"
    ANIMATED_WEBP = "animated_webp"
    GIF = "gif"
    VIDEO = "video"
    PLACEHOLDER = "placeholder"
