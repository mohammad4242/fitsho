from datetime import datetime, time
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.nutrition.enums import (
    BudgetStyle,
    CookingEquipment,
    CookingSkill,
    DietaryPattern,
    MealPreparationPreference,
    MedicalConditionCode,
    NutritionOnboardingStatus,
    NutritionPlanStyle,
    PhysicianReviewMode,
    PhysicianReviewStatus,
    PreferredVariety,
    SafetyOutcome,
    Weekday,
)


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


class FoodConstraintInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    details: str | None = Field(default=None, max_length=500)

    _normalize_text = field_validator("name", "details", mode="before")(normalize_optional_text)


class NutritionProfileInput(BaseModel):
    individual_monthly_food_budget_irr: int = Field(ge=0, le=100_000_000_000)
    budget_style: BudgetStyle
    meals_per_day: int = Field(ge=1, le=8)
    snacks_per_day: int = Field(ge=0, le=6)
    preferred_plan_start_day: Weekday
    plan_style: NutritionPlanStyle
    cooking_skill: CookingSkill
    maximum_cooking_time_minutes: int = Field(ge=0, le=360)
    cooking_frequency_per_week: int = Field(ge=0, le=7)
    meal_preparation_preference: MealPreparationPreference
    refrigerator_access: bool
    freezer_access: bool
    cooking_equipment: list[CookingEquipment] = Field(max_length=10)
    supplied_meals_per_week: int = Field(ge=0, le=35)
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
    preferred_variety: PreferredVariety
    maximum_meal_repetition_per_week: int = Field(ge=1, le=7)
    accepts_leftovers: bool
    accepts_batch_cooking: bool
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
    physician_review_required: bool
    created_at: datetime
    updated_at: datetime


class PhysicianReviewRequirementResponse(BaseModel):
    required: bool
    mode: PhysicianReviewMode
    status: PhysicianReviewStatus
    safety_decision_id: UUID
