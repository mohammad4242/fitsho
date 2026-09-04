from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.nutrition.enums import (
    BudgetStyle,
    CookingEquipment,
    CookingSkill,
    DailyActivityLevel,
    DietaryPattern,
    EstimateConfidence,
    FoodMeasurementBasis,
    FoodPortionUnit,
    MainMealCountBucket,
    MealCalculationMode,
    MealCategory,
    MealIngredientRole,
    MealPreparationPreference,
    MedicalConditionCode,
    MetabolicBasis,
    NutritionBudgetTier,
    NutritionDailyCheckInStatus,
    NutritionDietStyle,
    NutritionEstimateStatus,
    NutritionLabRequestStatus,
    NutritionMealFeedbackType,
    NutritionOnboardingStatus,
    NutritionPlanStyle,
    NutritionProgramSlotKind,
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
from app.profile.enums import FitnessGoal, TrainingIntensity


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
    target_weight_change_kg_per_week: Decimal | None = Field(
        default=None, ge=Decimal("0.3"), le=Decimal("2.0")
    )

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


class CatalogueNutrientInput(BaseModel):
    nutrient_code: str = Field(min_length=1, max_length=48)
    value_per_100g: float = Field(ge=0)
    unit: str = Field(min_length=1, max_length=24)
    unit_form: str = Field(default="nutrient_mass", min_length=1, max_length=48)
    source_name: str = Field(min_length=1, max_length=160)
    source_reference: str = Field(min_length=1, max_length=500)
    confidence: EstimateConfidence


class CatalogueFoodPortionInput(BaseModel):
    code: FoodPortionUnit
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    label_fa: str = Field(min_length=1, max_length=80)
    label_en: str = Field(min_length=1, max_length=80)
    grams: Decimal = Field(gt=0)
    is_default: bool = False
    sort_order: int = Field(default=0, ge=0)
    source_name: str = Field(min_length=1, max_length=160)
    source_reference: str = Field(min_length=1, max_length=500)


class CatalogueFoodWrite(BaseModel):
    slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9-]+$")
    name_fa: str = Field(min_length=1, max_length=160)
    name_en: str = Field(min_length=1, max_length=160)
    verification_status: str
    source_name: str = Field(min_length=1, max_length=160)
    source_reference: str = Field(min_length=1, max_length=500)
    source_food_id: str | None = Field(default=None, max_length=120)
    category: str = Field(default="uncategorized", min_length=1, max_length=64)
    measurement_basis: FoodMeasurementBasis = FoodMeasurementBasis.AS_PURCHASED
    canonical_quantity: float = Field(default=100, gt=0)
    canonical_unit: str = Field(default="g", min_length=1, max_length=16)
    edible_portion: float = Field(default=1, gt=0, le=1)
    data_version: str = Field(default="unversioned", min_length=1, max_length=64)
    source_access_date: date | None = None
    aliases: list[str] = Field(default_factory=list, max_length=50)
    dietary_patterns: list[str] = Field(
        default_factory=lambda: ["omnivore", "vegetarian", "vegan"],
        min_length=1,
        max_length=3,
    )
    roles: list[str] = Field(min_length=1, max_length=4)
    allergen_tags: list[str] = Field(default_factory=list, max_length=20)
    allergen_metadata_verified: bool = False
    nutrients: list[CatalogueNutrientInput] = Field(default_factory=list, max_length=64)
    portions: list[CatalogueFoodPortionInput] = Field(default_factory=list, max_length=12)


class CatalogueFoodResponse(CatalogueFoodWrite):
    id: UUID


class FoodCataloguePriceResponse(BaseModel):
    status: Literal["accepted", "not_found"]
    reference_price_irr: Decimal | None = None
    reference_unit: Literal["IRR_PER_KG", "IRR_PER_LITER", "IRR_PER_UNIT"] | None = None
    observed_at: datetime | None = None
    # Deprecated compatibility fields. Member clients must display the IRR fields above.
    reference_price_toman: Decimal | None = None
    canonical_unit: str | None = None
    accepted_at: datetime | None = None
    source: Literal["automatic", "manual_override"] | None = None


class FoodCatalogueNutrientBasis(BaseModel):
    quantity: Decimal
    unit: str


class FoodCatalogueSourceResponse(BaseModel):
    name: str
    reference: str
    source_food_id: str | None
    data_version: str
    access_date: date | None


class FoodCataloguePortionResponse(BaseModel):
    code: FoodPortionUnit
    quantity: Decimal
    label_fa: str
    label_en: str
    grams: Decimal
    is_default: bool
    source_name: str
    source_reference: str


class FoodCatalogueItemResponse(BaseModel):
    id: UUID
    slug: str
    name_fa: str
    name_en: str
    image_url: str | None
    category: str
    measurement_basis: FoodMeasurementBasis
    nutrient_basis: FoodCatalogueNutrientBasis
    macros: dict[str, Decimal | None]
    nutrients: list[CatalogueNutrientInput]
    portions: list[FoodCataloguePortionResponse]
    source: FoodCatalogueSourceResponse
    allergen_tags: list[str] = Field(default_factory=list)
    allergen_metadata_verified: bool = False


class AdminFoodCatalogueItemResponse(FoodCatalogueItemResponse):
    price: FoodCataloguePriceResponse


class FoodCatalogueImageResponse(BaseModel):
    image_url: str


class FoodCataloguePageResponse(BaseModel):
    items: list[FoodCatalogueItemResponse]
    page: int
    page_size: int
    total: int
    categories: list[str]


class AdminFoodCataloguePageResponse(BaseModel):
    items: list[AdminFoodCatalogueItemResponse]
    page: int
    page_size: int
    total: int
    categories: list[str]


class FoodPriceOverrideInput(BaseModel):
    reference_price_toman: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    canonical_unit: Literal["TOMAN_PER_KG", "TOMAN_PER_LITER", "TOMAN_PER_UNIT"]
    reason: str = Field(min_length=5, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 5:
            raise ValueError("Override reason is too short")
        return normalized


class FoodPriceOverrideResponse(BaseModel):
    id: UUID
    food_id: UUID
    reference_price_toman: Decimal
    canonical_unit: str
    reason: str
    source: Literal["manual_override"] = "manual_override"
    created_at: datetime


class SingleFoodPriceResearchQuoteResponse(BaseModel):
    source_name: str
    source_url: str
    source_domain: str
    product_title: str
    normal_price_toman: Decimal
    promotional_price_toman: Decimal | None = None
    package_quantity: Decimal
    package_unit: str
    match_accepted: bool


class SingleFoodPriceResearchResponse(BaseModel):
    food_slug: str
    food_name_fa: str
    candidate_reference_price_toman: Decimal | None = None
    canonical_unit: str | None = None
    quotes: list[SingleFoodPriceResearchQuoteResponse] = Field(default_factory=list)
    status: Literal["success", "no_quotes", "failed"]
    message: str | None = None


class CatalogueMealItemInput(BaseModel):
    food_id: UUID
    reference_grams: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    min_grams: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    max_grams: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    is_required: bool = True
    functional_role: MealIngredientRole | None = None

    @model_validator(mode="after")
    def validate_bounds(self) -> "CatalogueMealItemInput":
        if not self.min_grams <= self.reference_grams <= self.max_grams:
            raise ValueError("Ingredient grams must satisfy min <= reference <= max")
        return self


class PreparedRecipeIngredientInput(BaseModel):
    food_id: UUID
    reference_grams: Decimal = Field(ge=0, max_digits=20, decimal_places=8)
    min_grams: Decimal = Field(ge=0, max_digits=20, decimal_places=8)
    max_grams: Decimal = Field(ge=0, max_digits=20, decimal_places=8)
    is_required: bool = True

    @model_validator(mode="after")
    def validate_bounds(self) -> "PreparedRecipeIngredientInput":
        if not self.min_grams <= self.reference_grams <= self.max_grams:
            raise ValueError("Recipe ingredient grams must satisfy min <= reference <= max")
        if self.is_required and min(self.min_grams, self.reference_grams, self.max_grams) <= 0:
            raise ValueError("Required recipe ingredient quantities must be positive")
        return self


class PreparedRecipeRatioInput(BaseModel):
    numerator_food_id: UUID
    denominator_food_id: UUID
    min_ratio: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    max_ratio: Decimal = Field(gt=0, max_digits=20, decimal_places=8)

    @model_validator(mode="after")
    def validate_ratio(self) -> "PreparedRecipeRatioInput":
        if self.numerator_food_id == self.denominator_food_id:
            raise ValueError("Recipe ratio ingredients must be different")
        if self.min_ratio > self.max_ratio:
            raise ValueError("Recipe ratio must satisfy min <= max")
        return self


class PreparedRecipeYieldInput(BaseModel):
    method: Literal["proportional_reference_batch"]
    final_cooked_yield_grams: Decimal = Field(gt=0, max_digits=20, decimal_places=8)
    source_name: str = Field(min_length=1, max_length=160)
    source_reference: str = Field(min_length=1, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)


class PreparedRecipeDataGapInput(BaseModel):
    ingredient_name_fa: str = Field(min_length=1, max_length=160)
    ingredient_name_en: str = Field(min_length=1, max_length=160)
    message_fa: str = Field(min_length=1, max_length=500)
    message_en: str = Field(min_length=1, max_length=500)


class PreparedRecipeWrite(BaseModel):
    verification_status: Literal["draft", "verified", "retired"]
    source_name: str = Field(min_length=1, max_length=160)
    source_reference: str = Field(min_length=1, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)
    cooked_yield: PreparedRecipeYieldInput
    ingredients: list[PreparedRecipeIngredientInput] = Field(min_length=1, max_length=30)
    ratios: list[PreparedRecipeRatioInput] = Field(default_factory=list, max_length=50)
    data_gaps: list[PreparedRecipeDataGapInput] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def validate_collections(self) -> "PreparedRecipeWrite":
        food_ids = [item.food_id for item in self.ingredients]
        if len(food_ids) != len(set(food_ids)):
            raise ValueError("Recipe ingredients must be unique")
        ratio_pairs = [(item.numerator_food_id, item.denominator_food_id) for item in self.ratios]
        if len(ratio_pairs) != len(set(ratio_pairs)):
            raise ValueError("Recipe ratio constraints must be unique")
        return self


class CatalogueMealWrite(BaseModel):
    code: str = Field(min_length=2, max_length=20, pattern=r"^[A-Z][A-Z0-9-]*$")
    name_fa: str = Field(min_length=1, max_length=160)
    name_en: str = Field(min_length=1, max_length=160)
    category: MealCategory
    verification_status: Literal["draft", "verified", "retired"]
    calculation_mode: MealCalculationMode = MealCalculationMode.SIMPLE
    items: list[CatalogueMealItemInput] = Field(default_factory=list, max_length=20)
    prepared_recipe: PreparedRecipeWrite | None = None

    @field_validator("items")
    @classmethod
    def unique_foods(cls, values: list[CatalogueMealItemInput]) -> list[CatalogueMealItemInput]:
        if len({item.food_id for item in values}) != len(values):
            raise ValueError("Meal foods must be unique")
        return values

    @model_validator(mode="after")
    def validate_calculation_mode(self) -> "CatalogueMealWrite":
        if self.calculation_mode is MealCalculationMode.SIMPLE:
            if not self.items:
                raise ValueError("Simple meals require at least one food")
            if self.prepared_recipe is not None:
                raise ValueError("Simple meals cannot include a Prepared Recipe")
        elif self.prepared_recipe is None:
            raise ValueError("Prepared Recipe meals require a valid recipe")
        return self


class CatalogueMealItemResponse(BaseModel):
    food_id: UUID
    food_slug: str
    food_name_fa: str
    food_name_en: str
    reference_grams: float
    min_grams: float
    max_grams: float
    is_required: bool
    functional_role: MealIngredientRole | None


class PreparedRecipeIngredientResponse(BaseModel):
    food_id: UUID
    food_slug: str
    food_name_fa: str
    food_name_en: str
    reference_grams: float
    min_grams: float
    max_grams: float
    is_required: bool


class PreparedRecipeRatioResponse(BaseModel):
    numerator_food_id: UUID
    denominator_food_id: UUID
    min_ratio: float
    max_ratio: float


class PreparedRecipeYieldResponse(BaseModel):
    method: str
    reference_input_grams: float
    final_cooked_yield_grams: float
    source_name: str
    source_reference: str
    notes: str | None


class PreparedRecipePreviewResponse(BaseModel):
    final_cooked_yield_grams: float
    nutrients_per_100g: dict[str, float]
    estimated_cost_irr_per_100g: float | None
    price_reference_ids: list[str]


class PreparedRecipeResponse(BaseModel):
    id: UUID
    version: int
    verification_status: Literal["draft", "verified", "retired"]
    calculation_version: str
    source_name: str
    source_reference: str
    notes: str | None
    cooked_yield: PreparedRecipeYieldResponse
    ingredients: list[PreparedRecipeIngredientResponse]
    ratios: list[PreparedRecipeRatioResponse]
    data_gaps: list[PreparedRecipeDataGapInput]
    preview: PreparedRecipePreviewResponse


class SharedCatalogueMealResponse(BaseModel):
    id: UUID
    code: str
    name_fa: str
    name_en: str
    image_url: str | None
    category: MealCategory
    verification_status: Literal["draft", "verified", "retired"]
    calculation_mode: MealCalculationMode = MealCalculationMode.SIMPLE
    items: list[CatalogueMealItemResponse]


class SharedCatalogueMealPageResponse(BaseModel):
    items: list[SharedCatalogueMealResponse]
    categories: list[MealCategory]


class CatalogueMealResponse(SharedCatalogueMealResponse):
    prepared_recipe: PreparedRecipeResponse | None
    totals: dict[str, float | None]


class CatalogueMealPageResponse(BaseModel):
    items: list[CatalogueMealResponse]
    categories: list[MealCategory]


class CatalogueMealImageResponse(BaseModel):
    image_url: str


class NutritionProgramSlotWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: MealCategory
    kind: NutritionProgramSlotKind = NutritionProgramSlotKind.CATALOGUE_MEAL
    meal_id: UUID | None

    @model_validator(mode="after")
    def validate_relationship(self) -> "NutritionProgramSlotWrite":
        if self.kind is NutritionProgramSlotKind.CATALOGUE_MEAL and self.meal_id is None:
            raise ValueError("Catalogue meal slots require a Meal Catalogue relationship")
        if self.kind is NutritionProgramSlotKind.FREE_MEAL and self.meal_id is not None:
            raise ValueError("Free Meal slots cannot reference the Meal Catalogue")
        if (
            self.kind is NutritionProgramSlotKind.FREE_MEAL
            and self.category is not MealCategory.LUNCH
        ):
            raise ValueError("Free Meal replaces lunch")
        return self


class NutritionProgramDayWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_number: int = Field(ge=1, le=7)
    post_workout_enabled: bool = False
    slots: list[NutritionProgramSlotWrite] = Field(min_length=4, max_length=5)

    @model_validator(mode="after")
    def validate_slots(self) -> "NutritionProgramDayWrite":
        categories = [slot.category for slot in self.slots]
        if len(categories) != len(set(categories)):
            raise ValueError("Program day meal slots must be unique")
        required = {
            MealCategory.BREAKFAST,
            MealCategory.LUNCH,
            MealCategory.SNACK,
            MealCategory.DINNER,
        }
        if not required.issubset(categories):
            raise ValueError("Every program day requires breakfast, lunch, snack, and dinner")
        has_post_workout = MealCategory.POST_WORKOUT in categories
        if has_post_workout != self.post_workout_enabled:
            raise ValueError("Post-workout slot must match the day post-workout setting")
        return self


class NutritionProgramWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, min_length=1, max_length=20, pattern=r"^[A-Z0-9-]+$")
    name_fa: str = Field(min_length=1, max_length=160)
    name_en: str = Field(min_length=1, max_length=160)
    description_fa: str = Field(min_length=1, max_length=1000)
    description_en: str = Field(min_length=1, max_length=1000)
    diet_style: NutritionDietStyle
    budget_tier_hint: NutritionBudgetTier | None = None
    post_workout_enabled: bool = False
    days: list[NutritionProgramDayWrite] = Field(min_length=7, max_length=7)

    @model_validator(mode="after")
    def validate_week(self) -> "NutritionProgramWrite":
        if {day.day_number for day in self.days} != set(range(1, 8)):
            raise ValueError("Program must contain days 1 through 7 exactly once")
        if not self.post_workout_enabled and any(day.post_workout_enabled for day in self.days):
            raise ValueError("Daily post-workout cannot be enabled when globally disabled")
        return self


class NutritionProgramMealReference(BaseModel):
    id: UUID
    code: str
    name_fa: str
    name_en: str
    image_url: str | None
    category: MealCategory


class NutritionProgramSlotResponse(BaseModel):
    id: UUID
    kind: NutritionProgramSlotKind
    category: MealCategory
    meal: NutritionProgramMealReference | None


class NutritionProgramDayResponse(BaseModel):
    id: UUID
    day_number: int
    post_workout_enabled: bool
    slots: list[NutritionProgramSlotResponse]


class NutritionProgramResponse(BaseModel):
    id: UUID
    code: str
    slug: str
    name_fa: str
    name_en: str
    description_fa: str
    description_en: str
    diet_style: NutritionDietStyle
    budget_tier_hint: NutritionBudgetTier | None = None
    post_workout_enabled: bool
    is_active: bool
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
    days: list[NutritionProgramDayResponse]


class NutritionProgramPageResponse(BaseModel):
    items: list[NutritionProgramResponse]
    diet_styles: list[NutritionDietStyle]
    budget_tiers: list[NutritionBudgetTier] = Field(
        default_factory=lambda: list(NutritionBudgetTier)
    )


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
    input_snapshot: dict[str, object] = Field(default_factory=dict)


class PhysicianReviewRequirementResponse(BaseModel):
    required: bool
    mode: PhysicianReviewMode
    status: PhysicianReviewStatus
    safety_decision_id: UUID


class WeeklyPlanPreparedRecipeSummary(BaseModel):
    status: Literal["estimated", "verified"]
    nutrients_per_100g: dict[str, float]
    cost_irr_per_100g: float


class WeeklyPlanFoodResponse(BaseModel):
    food_id: UUID | None
    item_kind: Literal["food", "prepared_recipe"] = "food"
    slug: str
    name_fa: str
    name_en: str
    grams: float
    cost_irr: int
    nutrients: dict[str, float]
    prepared_recipe: WeeklyPlanPreparedRecipeSummary | None = None


class WeeklyPlanMealResponse(BaseModel):
    id: UUID
    catalogue_meal_id: UUID | None
    catalogue_meal_category: str | None
    name_fa: str | None
    name_en: str | None
    meal_code: str | None
    image_url: str | None
    slot_role: str
    slot_index: int
    target_distribution: dict[str, float]
    nutrient_totals: dict[str, float]
    cost_irr: int
    is_locked: bool
    foods: list[WeeklyPlanFoodResponse]


class WeeklyPlanFeedbackResponse(BaseModel):
    feedback: dict[UUID, NutritionMealFeedbackType]


class MealReplacementOptionResponse(BaseModel):
    id: UUID
    name_fa: str
    name_en: str
    meal_code: str
    image_url: str | None
    slot_role: str
    nutrient_totals: dict[str, float]
    cost_irr: int
    is_locked: bool


class MealReplacementOptionsResponse(BaseModel):
    target_meal_id: UUID
    options: list[MealReplacementOptionResponse]


class FoodReplacementOptionResponse(BaseModel):
    food_id: UUID
    slug: str
    name_fa: str
    name_en: str
    image_url: str | None
    grams: float
    cost_irr: int
    nutrients: dict[str, float]


class FoodReplacementOptionsResponse(BaseModel):
    target_meal_id: UUID
    target_food_id: UUID
    options: list[FoodReplacementOptionResponse]


class WeeklyPlanDayResponse(BaseModel):
    day_index: int
    plan_date: date
    nutrient_totals: dict[str, float]
    cost_irr: int
    meals: list[WeeklyPlanMealResponse]


class WeeklyPlanNutrientResponse(BaseModel):
    nutrient_code: str
    unit: str
    reference_kind: str | None
    preferred: float | None
    minimum_or_maximum: float | None
    planned: float
    difference_from_preferred: float | None
    difference_from_limit: float | None
    status: str
    reason_codes: list[str]
    data_confidence: str
    explanation_codes: list[str]


class WeeklyPlanResponse(BaseModel):
    id: UUID
    revision: int
    lifecycle_status: str
    is_user_visible: bool
    physician_approved: bool
    review_status: str
    physician_approved_at: datetime | None
    physician_display_name: str | None
    physician_user_visible_notes: str | None
    physician_change_summary: list[dict[str, object]]
    supersedes_plan_id: UUID | None
    start_date: date
    planner_policy_version: str
    planner_version: str
    scientific_policy_version: str
    formula_version: str
    weekly_cost_irr: int
    weekly_budget_irr: int
    budget_status: str
    warning_codes: list[str]
    explanation_codes: list[str]
    input_snapshot: dict[str, object]
    price_snapshot: dict[str, object]
    food_data_manifest: dict[str, object]
    repair_actions: list[dict[str, object]]
    nutrients: dict[str, WeeklyPlanNutrientResponse]
    days: list[WeeklyPlanDayResponse]
    created_at: datetime


class WeeklyPlanGenerationResponse(BaseModel):
    generation_id: UUID
    outcome: str
    reason_codes: list[str]
    warning_codes: list[str]
    plan: WeeklyPlanResponse | None


class WeeklyPlanHistoryItemResponse(BaseModel):
    id: UUID
    revision: int
    lifecycle_status: str
    review_status: str
    weekly_cost_irr: int
    weekly_budget_irr: int
    budget_status: str
    created_at: datetime


class MealLockInput(BaseModel):
    is_locked: bool


class MealFeedbackInput(BaseModel):
    feedback_type: NutritionMealFeedbackType
    notes: str | None = Field(default=None, max_length=1000)


class RemoveMealConfirmationInput(BaseModel):
    expected_plan_revision_id: UUID
    meal_id: UUID


class ReplaceMealInput(BaseModel):
    expected_plan_revision_id: UUID
    meal_id: UUID
    replacement_meal_id: UUID


class ReplaceFoodInput(BaseModel):
    expected_plan_revision_id: UUID
    meal_id: UUID
    food_id: UUID
    replacement_food_id: UUID


class PartialRegenerationInput(BaseModel):
    expected_plan_revision_id: UUID
    day_indexes: list[int] = Field(min_length=1, max_length=7)


class PhysicianPlanActionInput(BaseModel):
    expected_plan_revision_id: UUID
    action: str = Field(pattern="^(start_review|approve|request_changes|reject)$")
    notes: str | None = Field(default=None, max_length=2000)
    internal_notes: str | None = Field(default=None, max_length=4000)


PhysicianQueueView = Literal["pending", "claimed", "approved"]


class PhysicianReviewQueueItemResponse(BaseModel):
    review_id: UUID
    plan_id: UUID
    user_id: UUID
    member_display_name: str | None
    status: str
    priority: int
    physician_user_id: UUID | None
    requested_at: datetime
    target_review_by: datetime | None
    reviewed_at: datetime | None
    overdue: bool


class PhysicianFoodQuantityInput(BaseModel):
    expected_plan_revision_id: UUID
    meal_id: UUID
    food_id: UUID
    grams: float = Field(gt=0, le=5000)


class DailyCheckInInput(BaseModel):
    entry_date: date
    status: NutritionDailyCheckInStatus
    note: str | None = Field(default=None, max_length=1000)


class CatalogueConsumptionInput(BaseModel):
    entry_date: date
    food_id: UUID
    grams: float = Field(gt=0, le=5000)
    note: str | None = Field(default=None, max_length=1000)


class QuickApproximationInput(BaseModel):
    entry_date: date
    display_name: str = Field(min_length=1, max_length=160)
    calories: float = Field(gt=0, le=10000)
    protein_g: float | None = Field(default=None, ge=0, le=1000)


class FreeMealTrackingInput(BaseModel):
    entry_date: date
    calories: float = Field(gt=0, le=10000)
    protein_g: float = Field(ge=0, le=1000)
    carbohydrate_g: float = Field(ge=0, le=2000)
    fat_g: float = Field(ge=0, le=1000)


class ConsumptionEntryEditInput(BaseModel):
    grams: float | None = Field(default=None, gt=0, le=5000)
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    calories: float | None = Field(default=None, gt=0, le=10000)
    protein_g: float | None = Field(default=None, ge=0, le=1000)
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def require_edit(self) -> "ConsumptionEntryEditInput":
        if not self.model_fields_set:
            raise ValueError("At least one entry field is required")
        return self


class PlannedMealTrackingInput(BaseModel):
    entry_date: date
    status: Literal["consumed", "adjusted", "skipped"]
    portion_ratio: float | None = Field(default=None, gt=0, le=3)

    @model_validator(mode="after")
    def require_adjusted_ratio(self) -> "PlannedMealTrackingInput":
        if self.status == "adjusted" and self.portion_ratio is None:
            raise ValueError("Adjusted planned meal requires a portion ratio")
        return self


class FoodPhotoConfirmInput(BaseModel):
    entry_date: date


class FoodPhotoItemCorrectionInput(BaseModel):
    food_id: UUID | None = None
    estimated_amount: float | None = Field(default=None, gt=0, le=10000)
    remove: bool = False

    @model_validator(mode="after")
    def require_correction(self) -> "FoodPhotoItemCorrectionInput":
        if not self.remove and self.food_id is None and self.estimated_amount is None:
            raise ValueError("A photo item correction is required")
        return self


class TargetUpdateConfirmationInput(BaseModel):
    requested_goal: FitnessGoal
    confirmed: bool


class PhysicianLabRequestInput(BaseModel):
    expected_plan_revision_id: UUID
    requested_tests: list[str] = Field(min_length=1, max_length=30)
    user_visible_reason: str = Field(min_length=1, max_length=2000)


class PhysicianLabReviewInput(BaseModel):
    review_status: str = Field(pattern="^(reviewed|requires_follow_up)$")
    notes: str | None = Field(default=None, max_length=2000)


class PhysicianLabRequestTransitionInput(BaseModel):
    status: NutritionLabRequestStatus


class SupplementCatalogueInput(BaseModel):
    slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9-]+$")
    name_fa: str = Field(min_length=1, max_length=160)
    name_en: str = Field(min_length=1, max_length=160)
    verification_status: str = Field(pattern="^(draft|verified|retired)$")
    source_name: str = Field(min_length=1, max_length=160)
    source_reference: str = Field(min_length=1, max_length=500)
    active_ingredients: list[dict[str, object]] = Field(min_length=1, max_length=20)
    nutrient_contribution_per_unit: dict[str, object]
    contraindication_codes: list[str] = Field(default_factory=list, max_length=50)
    allergen_codes: list[str] = Field(default_factory=list, max_length=50)
    interaction_codes: list[str] = Field(default_factory=list, max_length=50)
    upper_bound_rules: list[dict[str, object]] = Field(default_factory=list, max_length=30)


class PhysicianSupplementOrderInput(BaseModel):
    supplement_id: UUID
    dose_amount: float = Field(gt=0, le=10000)
    dose_unit: str = Field(min_length=1, max_length=32)
    daily_units: float = Field(gt=0, le=100)
    frequency: str = Field(min_length=1, max_length=120)
    duration_days: int = Field(ge=1, le=730)
    starts_on: date | None = None
    instructions: str = Field(min_length=1, max_length=2000)
    rationale: str = Field(min_length=1, max_length=2000)
    rationale_user_visible: bool = True
    linked_gap_codes: list[str] = Field(default_factory=list, max_length=30)
    linked_lab_document_ids: list[UUID] = Field(default_factory=list, max_length=30)


class SupplementTransitionInput(BaseModel):
    status: str = Field(pattern="^(active|completed|discontinued|cancelled)$")


class SupplementAcknowledgementInput(BaseModel):
    adherence_note: str | None = Field(default=None, max_length=1000)
