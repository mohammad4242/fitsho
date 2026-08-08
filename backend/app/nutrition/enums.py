from enum import StrEnum


class SafetyOutcome(StrEnum):
    STANDARD_AUTOMATIC = "standard_automatic"
    AUTOMATIC_DRAFT_REQUIRES_PHYSICIAN_REVIEW = "automatic_draft_requires_physician_review"
    PHYSICIAN_MANUAL_PLAN_REQUIRED = "physician_manual_plan_required"
    UNSUPPORTED_OR_HARD_BLOCKED = "unsupported_or_hard_blocked"


class MedicalConditionCode(StrEnum):
    CONTROLLED_HYPERTENSION = "controlled_hypertension"
    LIPID_DISORDER = "lipid_disorder"
    TYPE_2_DIABETES_NON_INSULIN = "type_2_diabetes_non_insulin"
    STABLE_GASTROINTESTINAL = "stable_gastrointestinal"
    KIDNEY_DISEASE = "kidney_disease"
    DIALYSIS = "dialysis"
    LIVER_DISEASE = "liver_disease"
    INSULIN_TREATED_DIABETES = "insulin_treated_diabetes"
    OTHER = "other"


class BudgetStyle(StrEnum):
    STRICT = "strict"
    FLEXIBLE = "flexible"


class MainMealCountBucket(StrEnum):
    TWO = "two_main_meals"
    THREE = "three_main_meals"
    FOUR_OR_MORE = "four_or_more_main_meals"


class SnackCountBucket(StrEnum):
    ZERO = "zero_snacks"
    ONE = "one_snack"
    TWO = "two_snacks"
    THREE_OR_MORE = "three_or_more_snacks"


def main_meal_effective_slots(bucket: MainMealCountBucket) -> int:
    return {
        MainMealCountBucket.TWO: 2,
        MainMealCountBucket.THREE: 3,
        MainMealCountBucket.FOUR_OR_MORE: 4,
    }[bucket]


def snack_effective_slots(bucket: SnackCountBucket) -> int:
    return {
        SnackCountBucket.ZERO: 0,
        SnackCountBucket.ONE: 1,
        SnackCountBucket.TWO: 2,
        SnackCountBucket.THREE_OR_MORE: 3,
    }[bucket]


def main_meal_bucket_from_legacy(value: int) -> MainMealCountBucket:
    if value <= 2:
        return MainMealCountBucket.TWO
    if value == 3:
        return MainMealCountBucket.THREE
    return MainMealCountBucket.FOUR_OR_MORE


def snack_bucket_from_legacy(value: int) -> SnackCountBucket:
    if value <= 0:
        return SnackCountBucket.ZERO
    if value == 1:
        return SnackCountBucket.ONE
    if value == 2:
        return SnackCountBucket.TWO
    return SnackCountBucket.THREE_OR_MORE


class DailyActivityLevel(StrEnum):
    SEDENTARY = "sedentary"
    LIGHT = "light"
    MODERATE = "moderate"
    VERY_ACTIVE = "very_active"


class MetabolicBasis(StrEnum):
    FEMALE_COEFFICIENT = "female_coefficient"
    MALE_COEFFICIENT = "male_coefficient"


class StructuredExerciseType(StrEnum):
    RESISTANCE = "resistance"
    ENDURANCE = "endurance"
    MIXED = "mixed"
    OTHER = "other"


class StructuredExerciseSource(StrEnum):
    USER_REPORTED = "user_reported"
    TRAINING_PROFILE = "training_profile"
    ACTIVE_FITSHO_PLAN = "active_fitsho_plan"


class EstimateConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NutritionEstimateStatus(StrEnum):
    ACTIVE = "active"
    REVIEW_REQUIRED = "review_required"


class NutritionTargetMetric(StrEnum):
    BMR = "bmr"
    NON_EXERCISE_ENERGY = "non_exercise_energy"
    EXERCISE_ENERGY = "exercise_energy"
    TDEE = "tdee"
    GOAL_CALORIES = "goal_calories"
    PROTEIN = "protein"
    CARBOHYDRATE = "carbohydrate"
    TOTAL_FAT = "total_fat"
    FIBRE = "fibre"
    FREE_SUGAR = "free_sugar"
    ADDED_SUGAR = "added_sugar"
    SATURATED_FAT = "saturated_fat"
    TRANS_FAT = "trans_fat"
    SODIUM = "sodium"


class Weekday(StrEnum):
    SATURDAY = "saturday"
    SUNDAY = "sunday"
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"


class NutritionPlanStyle(StrEnum):
    ECONOMICAL = "economical"
    BALANCED = "balanced"
    SIMPLE = "simple"


class CookingSkill(StrEnum):
    NONE = "none"
    BASIC = "basic"
    CONFIDENT = "confident"


class MealPreparationPreference(StrEnum):
    DAILY = "daily"
    BATCH = "batch"
    MIXED = "mixed"
    NO_COOKING = "no_cooking"


class CookingEquipment(StrEnum):
    STOVE = "stove"
    OVEN = "oven"
    MICROWAVE = "microwave"
    AIR_FRYER = "air_fryer"
    RICE_COOKER = "rice_cooker"
    BLENDER = "blender"
    REFRIGERATOR = "refrigerator"


class FoodItemKind(StrEnum):
    AVAILABLE_AT_HOME = "available_at_home"
    FAVOURITE = "favourite"
    DISLIKED = "disliked"
    NEVER_SUGGEST = "never_suggest"
    REFUSED = "refused"
    ALLERGY = "allergy"
    INTOLERANCE = "intolerance"
    RELIGIOUS_CULTURAL_EXCLUSION = "religious_cultural_exclusion"


class DietaryPattern(StrEnum):
    OMNIVORE = "omnivore"
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"


class PreferredVariety(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class NutritionOnboardingStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class PhysicianReviewMode(StrEnum):
    NONE = "none"
    AUTOMATIC_DRAFT_REVIEW = "automatic_draft_review"
    MANUAL_PLAN = "manual_plan"
    BLOCKED = "blocked"


class PhysicianReviewStatus(StrEnum):
    NOT_REQUESTED = "not_requested"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"
