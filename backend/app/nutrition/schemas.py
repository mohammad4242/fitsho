from datetime import datetime, time
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.nutrition.enums import (
    BudgetStyle,
    CookingEquipment,
    CookingSkill,
    DailyActivityLevel,
    DietaryPattern,
    EstimateConfidence,
    MainMealCountBucket,
    MealPreparationPreference,
    MedicalConditionCode,
    MetabolicBasis,
    NutritionEstimateStatus,
    NutritionOnboardingStatus,
    NutritionPlanStyle,
    PhysicianReviewMode,
    PhysicianReviewStatus,
    PreferredVariety,
    SafetyOutcome,
    SnackCountBucket,
    StructuredExerciseSource,
    StructuredExerciseType,
    Weekday,
    main_meal_bucket_from_legacy,
    main_meal_effective_slots,
    snack_bucket_from_legacy,
    snack_effective_slots,
)
from app.profile.enums import TrainingIntensity


def normalize_optional_text(value: object) -> object:
    if not isinstance(value, str):
        return value
    normalized = value.strip()
    return normalized or None


class MedicalConditionInput(BaseModel):
    code: MedicalConditionCode
    details: str | None = Field(default=None, max_length=1000)

    _normalize_details = field_validator("details", mode="before")(normalize_optional_text)


class MedicationInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    dosage: str | None = Field(default=None, max_length=300)
    notes: str | None = Field(default=None, max_length=1000)

    _normalize_text = field_validator("name", "dosage", "notes", mode="before")(
        normalize_optional_text
    )


class SafetyProfileInput(BaseModel):
    conditions: list[MedicalConditionInput] = Field(default_factory=list, max_length=30)
    medications: list[MedicationInput] = Field(default_factory=list, max_length=30)
    dangerous_food_reaction_history: bool
    pregnant: bool
    breastfeeding: bool
    eating_disorder_diagnosed: bool
    eating_disorder_active_symptoms: bool
    emergency_or_danger_symptoms: bool
    complex_medication_food_interaction: bool = False
    physician_dietary_restrictions: str | None = Field(default=None, max_length=2000)
    other_relevant_condition: str | None = Field(default=None, max_length=1000)

    _normalize_text = field_validator(
        "physician_dietary_restrictions", "other_relevant_condition", mode="before"
    )(normalize_optional_text)

    @field_validator("conditions")
    @classmethod
    def unique_conditions(cls, values: list[MedicalConditionInput]) -> list[MedicalConditionInput]:
        if len({item.code for item in values}) != len(values):
            raise ValueError("Medical conditions must be unique")
        return values


class SafetyDecisionResponse(BaseModel):
    id: UUID
    outcome: SafetyOutcome
    policy_version: str
    reason_codes: list[str]
    requires_physician_review: bool
    can_continue_onboarding: bool
    message: str
    created_at: datetime


class SafetyEvaluationResponse(BaseModel):
    outcome: SafetyOutcome
    policy_version: str
    reason_codes: list[str]
    requires_physician_review: bool
    can_continue_onboarding: bool
    message: str


class FoodConstraintInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    details: str | None = Field(default=None, max_length=500)

    _normalize_text = field_validator("name", "details", mode="before")(normalize_optional_text)


class NutritionProfileInput(BaseModel):
    daily_activity_level: DailyActivityLevel
    metabolic_basis: MetabolicBasis | None = None
    individual_monthly_food_budget_irr: int = Field(ge=0, le=100_000_000_000)
    budget_style: BudgetStyle
    main_meal_count_bucket: MainMealCountBucket | None = None
    snack_count_bucket: SnackCountBucket | None = None
    # Deprecated compatibility inputs. New clients must use the typed buckets.
    meals_per_day: int | None = Field(default=None, ge=1, le=8)
    snacks_per_day: int | None = Field(default=None, ge=0, le=6)
    preferred_plan_start_day: Weekday
    # Cooking and preparation fields below are accepted only for old clients and are ignored.
    plan_style: NutritionPlanStyle = NutritionPlanStyle.BALANCED
    cooking_skill: CookingSkill = CookingSkill.NONE
    maximum_cooking_time_minutes: int = Field(default=0, ge=0, le=360)
    cooking_frequency_per_week: int = Field(default=0, ge=0, le=7)
    meal_preparation_preference: MealPreparationPreference = MealPreparationPreference.NO_COOKING
    refrigerator_access: bool = True
    freezer_access: bool = True
    cooking_equipment: list[CookingEquipment] = Field(default_factory=list, max_length=10)
    supplied_meals_per_week: int = Field(default=0, ge=0, le=35)
    supplied_meal_source: str | None = Field(default=None, max_length=300)
    foods_available_at_home: list[str] = Field(default_factory=list, max_length=100)
    favourite_foods: list[str] = Field(default_factory=list, max_length=100)
    disliked_foods: list[str] = Field(default_factory=list, max_length=100)
    never_suggest_foods: list[str] = Field(default_factory=list, max_length=100)
    refused_foods: list[str] = Field(default_factory=list, max_length=100)
    allergies: list[FoodConstraintInput] = Field(default_factory=list, max_length=100)
    intolerances: list[FoodConstraintInput] = Field(default_factory=list, max_length=100)
    dietary_pattern: DietaryPattern
    religious_cultural_exclusions: list[str] = Field(default_factory=list, max_length=100)
    preferred_variety: PreferredVariety = PreferredVariety.MEDIUM
    maximum_meal_repetition_per_week: int = Field(default=3, ge=1, le=7)
    accepts_leftovers: bool = True
    accepts_batch_cooking: bool = False
    work_shift_context: str | None = Field(default=None, max_length=500)
    daily_check_in_enabled: bool
    preferred_check_in_time: time | None = None

    _normalize_optional = field_validator(
        "supplied_meal_source", "work_shift_context", mode="before"
    )(normalize_optional_text)

    @field_validator(
        "foods_available_at_home",
        "favourite_foods",
        "disliked_foods",
        "never_suggest_foods",
        "refused_foods",
        "religious_cultural_exclusions",
        mode="before",
    )
    @classmethod
    def normalize_food_names(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        return [item.strip() if isinstance(item, str) else item for item in value]

    @model_validator(mode="after")
    def validate_unique_collections(self) -> "NutritionProfileInput":
        if self.main_meal_count_bucket is None:
            if self.meals_per_day is None:
                raise ValueError("Main-meal count is required")
            self.main_meal_count_bucket = main_meal_bucket_from_legacy(self.meals_per_day)
        if self.snack_count_bucket is None:
            if self.snacks_per_day is None:
                raise ValueError("Snack count is required")
            self.snack_count_bucket = snack_bucket_from_legacy(self.snacks_per_day)
        self.meals_per_day = main_meal_effective_slots(self.main_meal_count_bucket)
        self.snacks_per_day = snack_effective_slots(self.snack_count_bucket)
        if len(self.cooking_equipment) != len(set(self.cooking_equipment)):
            raise ValueError("Cooking equipment must be unique")
        collections: tuple[list[str], ...] = (
            self.foods_available_at_home,
            self.favourite_foods,
            self.disliked_foods,
            self.never_suggest_foods,
            self.refused_foods,
            self.religious_cultural_exclusions,
        )
        if any(any(not item for item in values) for values in collections):
            raise ValueError("Food names cannot be empty")
        if any(len(values) != len({item.casefold() for item in values}) for values in collections):
            raise ValueError("Food names must be unique within each collection")
        if self.daily_check_in_enabled and self.preferred_check_in_time is None:
            raise ValueError("Preferred check-in time is required when check-in is enabled")
        return self


class NutritionProfileResponse(NutritionProfileInput):
    user_id: UUID
    onboarding_status: NutritionOnboardingStatus
    currency: str
    weekly_budget_irr: int
    effective_main_meal_slots: int
    effective_snack_slots: int
    physician_review_required: bool
    created_at: datetime
    updated_at: datetime


class StructuredExerciseInput(BaseModel):
    trains: bool
    exercise_type: StructuredExerciseType | None = None
    days_per_week: int | None = Field(default=None, ge=1, le=7)
    minutes_per_session: int | None = Field(default=None, ge=1, le=360)
    intensity: TrainingIntensity | None = None

    @model_validator(mode="after")
    def validate_training_details(self) -> "StructuredExerciseInput":
        details = (
            self.exercise_type,
            self.days_per_week,
            self.minutes_per_session,
            self.intensity,
        )
        if self.trains and any(value is None for value in details):
            raise ValueError("Complete structured exercise details are required")
        if not self.trains and any(value is not None for value in details):
            raise ValueError("Exercise details must be empty when the member does not train")
        return self


class StructuredExerciseResponse(BaseModel):
    trains: bool
    exercise_type: StructuredExerciseType | None
    days_per_week: int | None
    minutes_per_session: int | None
    intensity: TrainingIntensity | None
    source: StructuredExerciseSource


class NutritionTargetResponse(BaseModel):
    unit: str
    minimum: float | None
    preferred: float | None
    preferred_maximum: float | None
    maximum: float | None
    confidence: EstimateConfidence
    source_ids: list[str]
    explanation_codes: list[str]


class NutritionMicronutrientTargetResponse(BaseModel):
    reference_kind: str
    target_value: float
    unit: str
    unit_form: str
    upper_limit_value: float | None
    upper_limit_kind: str | None
    upper_limit_scope: str
    aggregation_window: str
    policy_version: str
    source_reference: str
    applicable_population: str
    confidence: EstimateConfidence
    explanation_codes: list[str]


class NutritionEstimateResponse(BaseModel):
    id: UUID
    revision: int
    status: NutritionEstimateStatus
    policy_version: str
    formula_version: str
    confidence: EstimateConfidence
    confidence_reasons: list[str]
    is_stale: bool
    targets: dict[str, NutritionTargetResponse]
    micronutrients: dict[str, NutritionMicronutrientTargetResponse]
    created_at: datetime


class PhysicianReviewRequirementResponse(BaseModel):
    required: bool
    mode: PhysicianReviewMode
    status: PhysicianReviewStatus
    safety_decision_id: UUID
