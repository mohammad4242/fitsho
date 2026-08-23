from enum import StrEnum


class Goal(StrEnum):
    FAT_LOSS = "fat_loss"
    HYPERTROPHY = "hypertrophy"
    STRENGTH = "strength"
    MUSCLE_GAIN = "muscle_gain"
    BODY_RECOMPOSITION = "body_recomposition"
    GENERAL_FITNESS = "general_fitness"
    MUSCULAR_ENDURANCE = "muscular_endurance"


class TrainingExperience(StrEnum):
    FIRST_MONTH = "first_month"
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class TrainingStatus(StrEnum):
    NOVICE = "novice"
    EARLY_INTERMEDIATE = "early_intermediate"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ActivityLevel(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class RecoveryRating(StrEnum):
    POOR = "poor"
    AVERAGE = "average"
    GOOD = "good"


class PhysicalJobDemand(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class ImpactLimit(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class LoadLimit(StrEnum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class BalanceAbility(StrEnum):
    LIMITED = "limited"
    NORMAL = "normal"
    HIGH = "high"


class MedicalClearanceStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    CLEARED = "cleared"
    UNKNOWN = "unknown"


class SafetyStatus(StrEnum):
    CLEAR = "clear"
    CLEAR_WITH_MODIFICATIONS = "clear_with_modifications"
    REQUIRES_PROFESSIONAL_REVIEW = "requires_professional_review"
    STOP_AND_REFER = "stop_and_refer"


class ValidationStatus(StrEnum):
    VALID = "VALID"
    VALID_WITH_CONSTRAINTS = "VALID_WITH_CONSTRAINTS"
    INVALID = "INVALID"


class RedFlag(StrEnum):
    CHEST_PAIN = "chest_pain"
    SYNCOPE = "unexplained_syncope"
    DIZZINESS = "unexplained_dizziness"
    SHORTNESS_OF_BREATH = "unusual_shortness_of_breath"
    ACUTE_OR_WORSENING_PAIN = "acute_or_worsening_pain"
    NEW_NEUROLOGICAL_SYMPTOMS = "new_neurological_symptoms"
    NEW_WEAKNESS_OR_NUMBNESS = "new_weakness_or_numbness"
    RECENT_UNTREATED_INJURY = "recent_untreated_injury"
    FEVER_OR_ACUTE_ILLNESS = "fever_or_acute_illness"
    UNCONTROLLED_MEDICAL_CONDITION = "uncontrolled_medical_condition"


class SplitType(StrEnum):
    DYNAMIC_FALLBACK = "dynamic_fallback"
    FULL_BODY = "full_body"
    FULL_BODY_AB = "full_body_ab"
    FULL_BODY_ABC = "full_body_abc"
    FULL_BODY_FOUR = "full_body_four"
    UPPER_LOWER_FULL = "upper_lower_full"
    UPPER_LOWER = "upper_lower"
    UPPER_LOWER_SPECIALIZATION = "upper_lower_specialization"
    PUSH_PULL_LEGS = "push_pull_legs"
    PUSH_PULL_LEGS_UPPER_LOWER = "push_pull_legs_upper_lower"
    PUSH_PULL_LEGS_X2 = "push_pull_legs_x2"
    UPPER_LOWER_X3 = "upper_lower_x3"
    PHUL = "phul"
    BODY_PART_ROTATION = "body_part_rotation"


class GenerationErrorCode(StrEnum):
    UNSUPPORTED_RESISTANCE_TRAINING_DAYS = "UNSUPPORTED_RESISTANCE_TRAINING_DAYS"
    UNSATISFIED_CONSTRAINT = "UNSATISFIED_CONSTRAINT"
    NO_SAFE_EXERCISE_FOR_PATTERN = "NO_SAFE_EXERCISE_FOR_PATTERN"
    NO_AVAILABLE_EQUIPMENT_MATCH = "NO_AVAILABLE_EQUIPMENT_MATCH"
    INSUFFICIENT_ELIGIBLE_EXERCISES = "INSUFFICIENT_ELIGIBLE_EXERCISES"
    PROGRAM_REJECTED_SAFETY_STATUS = "PROGRAM_REJECTED_SAFETY_STATUS"
    PROGRAM_VALIDATION_FAILED = "PROGRAM_VALIDATION_FAILED"


class StabilityDemand(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class SkillDemand(StrEnum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"


class BodyPosition(StrEnum):
    STANDING = "standing"
    SEATED = "seated"
    LYING = "lying"
    SUPPORTED = "supported"


class Laterality(StrEnum):
    BILATERAL = "bilateral"
    UNILATERAL = "unilateral"
    NOT_APPLICABLE = "not_applicable"


class CardioIntensity(StrEnum):
    EASY = "easy"
    MODERATE = "moderate"
    VIGOROUS = "vigorous"


class CompatibilityLevel(StrEnum):
    PREFERRED = "PREFERRED"
    VALID_BUT_SUBOPTIMAL = "VALID_BUT_SUBOPTIMAL"
    HARD_INCOMPATIBLE = "HARD_INCOMPATIBLE"
