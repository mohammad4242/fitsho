from enum import StrEnum


class Sex(StrEnum):
    FEMALE = "female"
    MALE = "male"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class FitnessGoal(StrEnum):
    LOSE_WEIGHT = "lose_weight"
    BUILD_MUSCLE = "build_muscle"
    IMPROVE_FITNESS = "improve_fitness"
    MAINTAIN_WEIGHT = "maintain_weight"


class ExperienceLevel(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class TrainingLocation(StrEnum):
    HOME = "home"
    GYM = "gym"


class HomeTrainingSetup(StrEnum):
    BODYWEIGHT_ONLY = "bodyweight_only"
    DUMBBELLS_AVAILABLE = "dumbbells_available"


class TrainingCaution(StrEnum):
    LOWER_BACK = "lower_back"
    KNEE = "knee"
    SHOULDER = "shoulder"
    NECK = "neck"
    WRIST = "wrist"
    OTHER = "other"


class WorkoutGenerationMethod(StrEnum):
    FITSHO_COACH = "fitsho_coach"
    AI = "ai"
