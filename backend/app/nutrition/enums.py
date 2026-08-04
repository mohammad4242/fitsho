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
