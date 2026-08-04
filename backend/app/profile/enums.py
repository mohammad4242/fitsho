from enum import StrEnum


class ProductMode(StrEnum):
    TRAINING = "training"
    NUTRITION = "nutrition"
    BOTH = "both"


class ProfileCompletionState(StrEnum):
    PRODUCT_MODE_NOT_SELECTED = "product_mode_not_selected"
    SHARED_PROFILE_INCOMPLETE = "shared_profile_incomplete"
    TRAINING_ONBOARDING_INCOMPLETE = "training_onboarding_incomplete"
    NUTRITION_ONBOARDING_INCOMPLETE = "nutrition_onboarding_incomplete"
    MEDICAL_REVIEW_INFORMATION_INCOMPLETE = "medical_review_information_incomplete"
    TRAINING_READY = "training_ready"
    NUTRITION_DRAFT_READY = "nutrition_draft_ready"
    NUTRITION_PENDING_REVIEW = "nutrition_pending_review"
    NUTRITION_READY = "nutrition_ready"
    BOTH_READY = "both_ready"


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
