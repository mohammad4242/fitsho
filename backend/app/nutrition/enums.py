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


class MicronutrientReferenceKind(StrEnum):
    RDA = "rda"
    AI = "ai"
    EAR = "ear"
    UL = "ul"
    CDRR = "cdrr"
    MEDICAL_OVERRIDE = "medical_override"


class MicronutrientSex(StrEnum):
    ALL = "all"
    MALE = "male"
    FEMALE = "female"


class MicronutrientAggregationWindow(StrEnum):
    DAILY = "daily"
    WEEKLY_AVERAGE = "weekly_average"


class MicronutrientUpperLimitScope(StrEnum):
    NONE = "none"
    TOTAL_INTAKE = "total_intake"
    SUPPLEMENTAL_ONLY = "supplemental_only"
    SOURCE_FORM_SPECIFIC = "source_form_specific"


class FoodVerificationStatus(StrEnum):
    DRAFT = "draft"
    VERIFIED = "verified"
    RETIRED = "retired"


class FoodMeasurementBasis(StrEnum):
    RAW = "raw"
    DRY = "dry"
    AS_PURCHASED = "as_purchased"


class FoodPortionUnit(StrEnum):
    PIECE = "piece"
    PALM = "palm"
    CUP = "cup"
    TABLESPOON = "tablespoon"
    TEASPOON = "teaspoon"


class FoodRole(StrEnum):
    MAIN_PROTEIN = "main_protein"
    MAIN_STAPLE = "main_staple"
    SNACK = "snack"
    FLEXIBLE = "flexible"


class MealSlotRole(StrEnum):
    MAIN_MEAL = "main_meal"
    SNACK = "snack"


class MealCategory(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    POST_WORKOUT = "post_workout"
    SNACK = "snack"
    DINNER = "dinner"


class MealIngredientRole(StrEnum):
    PROTEIN = "protein"
    CARBOHYDRATE = "carbohydrate"
    FAT = "fat"
    FIBRE = "fibre"
    MICRONUTRIENT_SOURCE = "micronutrient_source"


class PriceProviderKind(StrEnum):
    DATABASE = "database"
    IMPORT = "import"
    SEED = "seed"
    PUBLIC_CATALOG = "public_catalog"
    FUTURE_API = "future_api"


class PriceQuoteStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    ESTIMATED = "estimated"
    UNAVAILABLE = "unavailable"


class PriceReferenceStatus(StrEnum):
    ACCEPTED = "accepted"
    NEEDS_REVIEW = "needs_review"
    UNAVAILABLE = "unavailable"


class PriceUpdateRunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    SKIPPED = "skipped"


class PriceUpdateTriggerKind(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    CATCH_UP = "catch_up"


class NutritionPlanGenerationOutcome(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SAFETY_BLOCKED = "safety_blocked"
    INFEASIBLE = "infeasible"
    TARGET_INFEASIBLE = "target_infeasible"
    LIVE_PRICE_UNAVAILABLE = "live_price_unavailable"


class NutritionPlanLifecycleStatus(StrEnum):
    DRAFT = "draft"
    GENERATED = "generated"
    PENDING_PHYSICIAN_REVIEW = "pending_physician_review"
    PHYSICIAN_REVIEW_IN_PROGRESS = "physician_review_in_progress"
    AWAITING_LAB_INFORMATION = "awaiting_lab_information"
    CHANGES_REQUESTED = "changes_requested"
    PHYSICIAN_APPROVED = "physician_approved"
    ACTIVE = "active"
    ARCHIVED = "archived"
    REJECTED = "rejected"


class NutritionPlanReviewStatus(StrEnum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    AWAITING_LAB_INFORMATION = "awaiting_lab_information"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    INVALIDATED_BY_REVISION = "invalidated_by_revision"


class NutritionPlanChangeKind(StrEnum):
    CONSUMPTION_ONLY = "consumption_only"
    PLAN_CONTROL_METADATA = "plan_control_metadata"
    PLAN_DEFINING = "plan_defining"


class NutritionMealFeedbackType(StrEnum):
    LIKED = "liked"
    DISLIKED = "disliked"
    DO_NOT_SUGGEST_AGAIN = "do_not_suggest_again"
    PREFER_MORE_OFTEN = "prefer_more_often"
    TOO_LARGE = "too_large"
    TOO_SMALL = "too_small"


class NutritionLabRequestStatus(StrEnum):
    REQUESTED = "requested"
    UPLOADED = "uploaded"
    REVIEWED = "reviewed"
    CANCELLED = "cancelled"


class NutritionSupplementOrderStatus(StrEnum):
    DRAFT = "draft"
    PRESCRIBED = "prescribed"
    ACTIVE = "active"
    COMPLETED = "completed"
    DISCONTINUED = "discontinued"
    CANCELLED = "cancelled"


class NutritionDailyCheckInStatus(StrEnum):
    ON_PLAN = "on_plan"
    MOSTLY_ON_PLAN = "mostly_on_plan"
    OFF_PLAN = "off_plan"
    NOT_RECORDED = "not_recorded"


class NutritionConsumptionSource(StrEnum):
    PLANNED_CONFIRMED = "planned_confirmed"
    PLANNED_ADJUSTED = "planned_adjusted"
    CATALOGUE_MANUAL = "catalogue_manual"
    PHOTO_ESTIMATED_CONFIRMED = "photo_estimated_confirmed"
    PHOTO_ESTIMATED_EDITED = "photo_estimated_edited"
    QUICK_APPROXIMATION = "quick_approximation"
    PROFESSIONAL_ENTRY = "professional_entry"


class NutritionPlanBudgetStatus(StrEnum):
    WITHIN_BUDGET = "within_budget"
    FLEXIBLE_OVERAGE = "flexible_overage"
    OVER_BUDGET = "over_budget"


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
