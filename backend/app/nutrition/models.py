# ruff: noqa: E501
from datetime import date, datetime, time
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.nutrition.enums import (
    BudgetStyle,
    CookingEquipment,
    CookingSkill,
    DailyActivityLevel,
    DietaryPattern,
    EstimateConfidence,
    FoodItemKind,
    FoodRole,
    FoodVerificationStatus,
    MainMealCountBucket,
    MealPreparationPreference,
    MealSlotRole,
    MedicalConditionCode,
    MetabolicBasis,
    MicronutrientAggregationWindow,
    MicronutrientReferenceKind,
    MicronutrientSex,
    MicronutrientUpperLimitScope,
    NutritionEstimateStatus,
    NutritionOnboardingStatus,
    NutritionPlanBudgetStatus,
    NutritionPlanGenerationOutcome,
    NutritionPlanLifecycleStatus,
    NutritionPlanReviewStatus,
    NutritionPlanStyle,
    NutritionTargetMetric,
    PhysicianReviewMode,
    PhysicianReviewStatus,
    PreferredVariety,
    PriceProviderKind,
    PriceQuoteStatus,
    PriceReferenceStatus,
    PriceUpdateRunStatus,
    SafetyOutcome,
    SnackCountBucket,
    StructuredExerciseSource,
    StructuredExerciseType,
    Weekday,
)
from app.profile.enums import TrainingIntensity


def enum_values(members: type[StrEnum]) -> list[str]:
    return [member.value for member in members]


def enum_column(members: type[StrEnum], name: str) -> Enum:
    return Enum(
        members,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        values_callable=enum_values,
        name=name,
    )


class MedicalConditionPolicy(Base):
    __tablename__ = "medical_condition_policies"

    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NutritionPolicyVersion(Base):
    __tablename__ = "nutrition_policy_versions"

    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    formula_version: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    source_manifest: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MicronutrientPolicyVersion(Base):
    __tablename__ = "nutrition_micronutrient_policy_versions"

    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    source_manifest: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    adequacy_scoring: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    completeness_thresholds: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    repair_tolerances: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    medical_override_precedence: Mapped[str] = mapped_column(String(300), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MicronutrientSource(Base):
    __tablename__ = "nutrition_micronutrient_sources"

    source_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    organization: Mapped[str] = mapped_column(String(160), nullable=False)
    reference_url: Mapped[str] = mapped_column(String(500), nullable=False)
    publication_date: Mapped[date | None] = mapped_column()
    access_date: Mapped[date] = mapped_column(nullable=False)
    policy_version: Mapped[str] = mapped_column(
        ForeignKey("nutrition_micronutrient_policy_versions.version", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(String(1000))


class MicronutrientReference(Base):
    __tablename__ = "nutrition_micronutrient_references"
    __table_args__ = (
        CheckConstraint("age_min >= 0", name="ck_nutrition_micro_refs_age_min"),
        CheckConstraint(
            "age_max IS NULL OR age_max >= age_min", name="ck_nutrition_micro_refs_age_order"
        ),
        CheckConstraint("target_value >= 0", name="ck_nutrition_micro_refs_target_nonnegative"),
        UniqueConstraint(
            "policy_version",
            "nutrient_code",
            "reference_kind",
            "age_min",
            "age_max",
            "sex",
            "life_stage",
            "dietary_pattern_modifier",
            name="uq_nutrition_micro_refs_population",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    policy_version: Mapped[str] = mapped_column(
        ForeignKey("nutrition_micronutrient_policy_versions.version", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    nutrient_code: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    reference_kind: Mapped[MicronutrientReferenceKind] = mapped_column(
        enum_column(MicronutrientReferenceKind, "ck_nutrition_micro_refs_kind_values"),
        nullable=False,
    )
    target_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    unit: Mapped[str] = mapped_column(String(24), nullable=False)
    unit_form: Mapped[str] = mapped_column(String(48), nullable=False, default="unspecified")
    unit_conversion: Mapped[dict[str, object] | None] = mapped_column(JSON)
    age_min: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    age_max: Mapped[int | None] = mapped_column(SmallInteger)
    sex: Mapped[MicronutrientSex] = mapped_column(
        enum_column(MicronutrientSex, "ck_nutrition_micro_refs_sex_values"), nullable=False
    )
    life_stage: Mapped[str] = mapped_column(String(48), nullable=False, default="adult")
    dietary_pattern_modifier: Mapped[str] = mapped_column(
        String(48), nullable=False, default="none"
    )
    modifier_multiplier_or_delta: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    upper_limit_scope: Mapped[MicronutrientUpperLimitScope] = mapped_column(
        enum_column(MicronutrientUpperLimitScope, "ck_nutrition_micro_refs_ul_scope_values"),
        nullable=False,
    )
    aggregation_window: Mapped[MicronutrientAggregationWindow] = mapped_column(
        enum_column(MicronutrientAggregationWindow, "ck_nutrition_micro_refs_window_values"),
        nullable=False,
    )
    source_organization: Mapped[str] = mapped_column(String(160), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    source_date: Mapped[date | None] = mapped_column()
    access_date: Mapped[date] = mapped_column(nullable=False)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("nutrition_micronutrient_sources.source_id", ondelete="RESTRICT"),
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(String(1000))


class NutritionMedicalProfile(Base):
    __tablename__ = "nutrition_medical_profiles"
    __table_args__ = (
        CheckConstraint(
            "physician_dietary_restrictions IS NULL OR "
            "char_length(physician_dietary_restrictions) <= 2000",
            name="ck_nutrition_medical_profiles_restrictions_length",
        ),
        CheckConstraint(
            "other_relevant_condition IS NULL OR char_length(other_relevant_condition) <= 1000",
            name="ck_nutrition_medical_profiles_other_length",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"), primary_key=True
    )
    dangerous_food_reaction_history: Mapped[bool] = mapped_column(Boolean, nullable=False)
    pregnant: Mapped[bool] = mapped_column(Boolean, nullable=False)
    breastfeeding: Mapped[bool] = mapped_column(Boolean, nullable=False)
    eating_disorder_diagnosed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    eating_disorder_active_symptoms: Mapped[bool] = mapped_column(Boolean, nullable=False)
    emergency_or_danger_symptoms: Mapped[bool] = mapped_column(Boolean, nullable=False)
    complex_medication_food_interaction: Mapped[bool] = mapped_column(Boolean, nullable=False)
    physician_dietary_restrictions: Mapped[str | None] = mapped_column(Text)
    other_relevant_condition: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class NutritionMedicalCondition(Base):
    __tablename__ = "nutrition_medical_conditions"
    __table_args__ = (
        UniqueConstraint("user_id", "code", name="uq_nutrition_medical_conditions_user_code"),
        CheckConstraint(
            "details IS NULL OR char_length(details) <= 1000",
            name="ck_nutrition_medical_conditions_details_length",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_medical_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[MedicalConditionCode] = mapped_column(
        enum_column(MedicalConditionCode, "ck_nutrition_medical_conditions_code_values"),
        nullable=False,
    )
    details: Mapped[str | None] = mapped_column(Text)


class NutritionMedication(Base):
    __tablename__ = "nutrition_medications"
    __table_args__ = (
        CheckConstraint(
            "char_length(btrim(name)) BETWEEN 1 AND 160", name="ck_nutrition_medications_name"
        ),
        CheckConstraint(
            "dosage IS NULL OR char_length(dosage) <= 300", name="ck_nutrition_medications_dosage"
        ),
        CheckConstraint(
            "notes IS NULL OR char_length(notes) <= 1000", name="ck_nutrition_medications_notes"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_medical_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    dosage: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)


class NutritionSafetyDecision(Base):
    __tablename__ = "nutrition_safety_decisions"
    __table_args__ = (
        UniqueConstraint("user_id", "revision", name="uq_nutrition_safety_decisions_user_revision"),
        CheckConstraint("revision > 0", name="ck_nutrition_safety_decisions_revision_positive"),
        Index("ix_nutrition_safety_decisions_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_medical_profiles.user_id", ondelete="CASCADE"), nullable=False
    )
    medical_condition_policy_version: Mapped[str] = mapped_column(
        ForeignKey("medical_condition_policies.version", ondelete="RESTRICT"), nullable=False
    )
    revision: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    outcome: Mapped[SafetyOutcome] = mapped_column(
        enum_column(SafetyOutcome, "ck_nutrition_safety_decisions_outcome_values"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reasons: Mapped[list["NutritionSafetyReason"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="NutritionSafetyReason.code"
    )


class NutritionSafetyReason(Base):
    __tablename__ = "nutrition_safety_reasons"

    safety_decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_safety_decisions.id", ondelete="CASCADE"), primary_key=True
    )
    code: Mapped[str] = mapped_column(String(100), primary_key=True)


class NutritionProfile(Base):
    __tablename__ = "nutrition_profiles"
    __table_args__ = (
        CheckConstraint(
            "individual_monthly_food_budget_irr BETWEEN 0 AND 100000000000",
            name="ck_nutrition_profiles_budget_range",
        ),
        CheckConstraint("meals_per_day BETWEEN 1 AND 8", name="ck_nutrition_profiles_meals_range"),
        CheckConstraint(
            "snacks_per_day BETWEEN 0 AND 6", name="ck_nutrition_profiles_snacks_range"
        ),
        CheckConstraint(
            "maximum_cooking_time_minutes BETWEEN 0 AND 360",
            name="ck_nutrition_profiles_cooking_time_range",
        ),
        CheckConstraint(
            "cooking_frequency_per_week BETWEEN 0 AND 7",
            name="ck_nutrition_profiles_cooking_frequency_range",
        ),
        CheckConstraint(
            "supplied_meals_per_week BETWEEN 0 AND 35",
            name="ck_nutrition_profiles_supplied_meals_range",
        ),
        CheckConstraint(
            "maximum_meal_repetition_per_week BETWEEN 1 AND 7",
            name="ck_nutrition_profiles_repetition_range",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"), primary_key=True
    )
    onboarding_status: Mapped[NutritionOnboardingStatus] = mapped_column(
        enum_column(NutritionOnboardingStatus, "ck_nutrition_profiles_status_values"),
        nullable=False,
    )
    daily_activity_level: Mapped[DailyActivityLevel] = mapped_column(
        enum_column(DailyActivityLevel, "ck_nutrition_profiles_daily_activity_level_values"),
        nullable=False,
    )
    metabolic_basis: Mapped[MetabolicBasis | None] = mapped_column(
        enum_column(MetabolicBasis, "ck_nutrition_profiles_metabolic_basis_values")
    )
    individual_monthly_food_budget_irr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    budget_style: Mapped[BudgetStyle] = mapped_column(
        enum_column(BudgetStyle, "ck_nutrition_profiles_budget_style_values"), nullable=False
    )
    meals_per_day: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    snacks_per_day: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    main_meal_count_bucket: Mapped[MainMealCountBucket] = mapped_column(
        enum_column(MainMealCountBucket, "ck_nutrition_profiles_main_meal_bucket_values"),
        nullable=False,
        server_default="three_main_meals",
    )
    snack_count_bucket: Mapped[SnackCountBucket] = mapped_column(
        enum_column(SnackCountBucket, "ck_nutrition_profiles_snack_bucket_values"),
        nullable=False,
        server_default="one_snack",
    )
    effective_main_meal_slots: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default="3"
    )
    effective_snack_slots: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default="1"
    )
    preferred_plan_start_day: Mapped[Weekday] = mapped_column(
        enum_column(Weekday, "ck_nutrition_profiles_start_day_values"), nullable=False
    )
    plan_style: Mapped[NutritionPlanStyle] = mapped_column(
        enum_column(NutritionPlanStyle, "ck_nutrition_profiles_plan_style_values"), nullable=False
    )
    cooking_skill: Mapped[CookingSkill] = mapped_column(
        enum_column(CookingSkill, "ck_nutrition_profiles_cooking_skill_values"), nullable=False
    )
    maximum_cooking_time_minutes: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    cooking_frequency_per_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    meal_preparation_preference: Mapped[MealPreparationPreference] = mapped_column(
        enum_column(MealPreparationPreference, "ck_nutrition_profiles_meal_prep_values"),
        nullable=False,
    )
    refrigerator_access: Mapped[bool] = mapped_column(Boolean, nullable=False)
    freezer_access: Mapped[bool] = mapped_column(Boolean, nullable=False)
    supplied_meals_per_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    supplied_meal_source: Mapped[str | None] = mapped_column(String(300))
    dietary_pattern: Mapped[DietaryPattern] = mapped_column(
        enum_column(DietaryPattern, "ck_nutrition_profiles_dietary_pattern_values"), nullable=False
    )
    preferred_variety: Mapped[PreferredVariety] = mapped_column(
        enum_column(PreferredVariety, "ck_nutrition_profiles_variety_values"), nullable=False
    )
    maximum_meal_repetition_per_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    accepts_leftovers: Mapped[bool] = mapped_column(Boolean, nullable=False)
    accepts_batch_cooking: Mapped[bool] = mapped_column(Boolean, nullable=False)
    work_shift_context: Mapped[str | None] = mapped_column(String(500))
    daily_check_in_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    preferred_check_in_time: Mapped[time | None] = mapped_column(Time)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class NutritionStructuredExercise(Base):
    __tablename__ = "nutrition_structured_exercises"
    __table_args__ = (
        CheckConstraint(
            "(trains = false AND exercise_type IS NULL AND days_per_week IS NULL "
            "AND minutes_per_session IS NULL AND intensity IS NULL) OR "
            "(trains = true AND exercise_type IS NOT NULL AND days_per_week IS NOT NULL "
            "AND minutes_per_session IS NOT NULL AND intensity IS NOT NULL)",
            name="ck_nutrition_structured_exercises_complete_when_training",
        ),
        CheckConstraint(
            "days_per_week IS NULL OR days_per_week BETWEEN 1 AND 7",
            name="ck_nutrition_structured_exercises_days_range",
        ),
        CheckConstraint(
            "minutes_per_session IS NULL OR minutes_per_session BETWEEN 1 AND 360",
            name="ck_nutrition_structured_exercises_minutes_range",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_profiles.user_id", ondelete="CASCADE"), primary_key=True
    )
    trains: Mapped[bool] = mapped_column(Boolean, nullable=False)
    exercise_type: Mapped[StructuredExerciseType | None] = mapped_column(
        enum_column(
            StructuredExerciseType,
            "ck_nutrition_structured_exercises_type_values",
        )
    )
    days_per_week: Mapped[int | None] = mapped_column(SmallInteger)
    minutes_per_session: Mapped[int | None] = mapped_column(SmallInteger)
    intensity: Mapped[TrainingIntensity | None] = mapped_column(
        enum_column(TrainingIntensity, "ck_nutrition_structured_exercises_intensity_values")
    )
    source: Mapped[StructuredExerciseSource] = mapped_column(
        enum_column(
            StructuredExerciseSource,
            "ck_nutrition_structured_exercises_source_values",
        ),
        nullable=False,
    )
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class NutritionEstimate(Base):
    __tablename__ = "nutrition_estimates"
    __table_args__ = (
        UniqueConstraint("user_id", "revision", name="uq_nutrition_estimates_user_revision"),
        UniqueConstraint(
            "user_id",
            "input_signature",
            "policy_version",
            name="uq_nutrition_estimates_user_signature_policy",
        ),
        CheckConstraint("revision > 0", name="ck_nutrition_estimates_revision_positive"),
        CheckConstraint(
            "char_length(input_signature) = 64",
            name="ck_nutrition_estimates_signature_length",
        ),
        Index("ix_nutrition_estimates_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_profiles.user_id", ondelete="CASCADE"), nullable=False
    )
    safety_decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_safety_decisions.id", ondelete="RESTRICT"), nullable=False
    )
    policy_version: Mapped[str] = mapped_column(
        ForeignKey("nutrition_policy_versions.version", ondelete="RESTRICT"), nullable=False
    )
    formula_version: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    input_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    input_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    status: Mapped[NutritionEstimateStatus] = mapped_column(
        enum_column(NutritionEstimateStatus, "ck_nutrition_estimates_status_values"),
        nullable=False,
    )
    overall_confidence: Mapped[EstimateConfidence] = mapped_column(
        enum_column(EstimateConfidence, "ck_nutrition_estimates_confidence_values"),
        nullable=False,
    )
    confidence_reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    targets: Mapped[list["NutritionEstimateTarget"]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="NutritionEstimateTarget.metric",
    )
    micronutrient_targets: Mapped[list["NutritionEstimateMicronutrientTarget"]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="NutritionEstimateMicronutrientTarget.nutrient_code",
    )


class NutritionEstimateTarget(Base):
    __tablename__ = "nutrition_estimate_targets"
    __table_args__ = (
        CheckConstraint(
            "(minimum_value IS NULL OR minimum_value >= 0) AND "
            "(preferred_value IS NULL OR preferred_value >= 0) AND "
            "(preferred_maximum_value IS NULL OR preferred_maximum_value >= 0) AND "
            "(maximum_value IS NULL OR maximum_value >= 0)",
            name="ck_nutrition_estimate_targets_nonnegative",
        ),
    )

    estimate_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_estimates.id", ondelete="CASCADE"), primary_key=True
    )
    metric: Mapped[NutritionTargetMetric] = mapped_column(
        enum_column(NutritionTargetMetric, "ck_nutrition_estimate_targets_metric_values"),
        primary_key=True,
    )
    unit: Mapped[str] = mapped_column(String(24), nullable=False)
    minimum_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    preferred_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    preferred_maximum_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    maximum_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    confidence: Mapped[EstimateConfidence] = mapped_column(
        enum_column(EstimateConfidence, "ck_nutrition_estimate_targets_confidence_values"),
        nullable=False,
    )
    source_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    applicable_population: Mapped[str] = mapped_column(String(200), nullable=False)
    rounding_rule: Mapped[str] = mapped_column(String(100), nullable=False)
    explanation_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class NutritionEstimateMicronutrientTarget(Base):
    __tablename__ = "nutrition_estimate_micronutrient_targets"
    __table_args__ = (
        CheckConstraint("target_value >= 0", name="ck_nutrition_estimate_micro_target_nonnegative"),
        CheckConstraint(
            "upper_limit_value IS NULL OR upper_limit_value >= 0",
            name="ck_nutrition_estimate_micro_upper_nonnegative",
        ),
        UniqueConstraint(
            "estimate_id", "nutrient_code", name="uq_nutrition_estimate_micro_nutrient"
        ),
    )

    estimate_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_estimates.id", ondelete="CASCADE"), primary_key=True
    )
    nutrient_code: Mapped[str] = mapped_column(String(48), primary_key=True)
    reference_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    target_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    unit: Mapped[str] = mapped_column(String(24), nullable=False)
    unit_form: Mapped[str] = mapped_column(String(48), nullable=False)
    upper_limit_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    upper_limit_kind: Mapped[str | None] = mapped_column(String(24))
    upper_limit_scope: Mapped[str] = mapped_column(String(32), nullable=False)
    aggregation_window: Mapped[str] = mapped_column(String(24), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    applicable_population: Mapped[str] = mapped_column(String(200), nullable=False)
    confidence: Mapped[EstimateConfidence] = mapped_column(
        enum_column(EstimateConfidence, "ck_nutrition_estimate_micro_confidence_values"),
        nullable=False,
    )
    explanation_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class NutritionCatalogueFood(Base):
    __tablename__ = "nutrition_catalogue_foods"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name_fa: Mapped[str] = mapped_column(String(160), nullable=False)
    name_en: Mapped[str] = mapped_column(String(160), nullable=False)
    verification_status: Mapped[FoodVerificationStatus] = mapped_column(
        enum_column(FoodVerificationStatus, "ck_nutrition_catalogue_food_status_values"),
        nullable=False,
    )
    source_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    source_food_id: Mapped[str | None] = mapped_column(String(120))
    dietary_patterns: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: ["omnivore", "vegetarian", "vegan"],
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    roles: Mapped[list["NutritionCatalogueFoodRole"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )
    compositions: Mapped[list["NutritionFoodComposition"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )


class NutritionCatalogueFoodRole(Base):
    __tablename__ = "nutrition_catalogue_food_roles"

    food_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_catalogue_foods.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[FoodRole] = mapped_column(
        enum_column(FoodRole, "ck_nutrition_catalogue_food_roles_values"), primary_key=True
    )


class NutritionFoodComposition(Base):
    __tablename__ = "nutrition_food_compositions"
    __table_args__ = (
        UniqueConstraint("food_id", "nutrient_code", name="uq_nutrition_food_composition"),
        CheckConstraint("value_per_100g >= 0", name="ck_nutrition_food_composition_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    food_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_catalogue_foods.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nutrient_code: Mapped[str] = mapped_column(String(48), nullable=False)
    value_per_100g: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    unit: Mapped[str] = mapped_column(String(24), nullable=False)
    unit_form: Mapped[str] = mapped_column(String(48), nullable=False, default="nutrient_mass")
    source_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    confidence: Mapped[EstimateConfidence] = mapped_column(
        enum_column(EstimateConfidence, "ck_nutrition_food_composition_confidence_values"),
        nullable=False,
    )


class NutritionCatalogueMeal(Base):
    __tablename__ = "nutrition_catalogue_meals"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name_fa: Mapped[str] = mapped_column(String(160), nullable=False)
    name_en: Mapped[str] = mapped_column(String(160), nullable=False)
    slot_role: Mapped[MealSlotRole] = mapped_column(
        enum_column(MealSlotRole, "ck_nutrition_catalogue_meal_slot_values"), nullable=False
    )
    verification_status: Mapped[FoodVerificationStatus] = mapped_column(
        enum_column(FoodVerificationStatus, "ck_nutrition_catalogue_meal_status_values"),
        nullable=False,
    )
    items: Mapped[list["NutritionCatalogueMealItem"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )


class NutritionCatalogueMealItem(Base):
    __tablename__ = "nutrition_catalogue_meal_items"
    __table_args__ = (
        CheckConstraint("grams > 0", name="ck_nutrition_catalogue_meal_item_grams_positive"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    meal_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_catalogue_meals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    food_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_catalogue_foods.id", ondelete="RESTRICT"), nullable=False
    )
    grams: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)


class NutritionPriceProvider(Base):
    __tablename__ = "nutrition_price_providers"
    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[PriceProviderKind] = mapped_column(
        enum_column(PriceProviderKind, "ck_nutrition_price_provider_kind_values"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=100)
    fresh_hours: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=24)
    stale_hours: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=168)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(500))


class NutritionFoodPriceMapping(Base):
    __tablename__ = "nutrition_food_price_mappings"
    __table_args__ = (
        UniqueConstraint(
            "provider_code", "provider_product_id", name="uq_price_mapping_provider_product"
        ),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    food_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_catalogue_foods.id", ondelete="CASCADE"), nullable=False
    )
    provider_code: Mapped[str] = mapped_column(
        ForeignKey("nutrition_price_providers.code", ondelete="CASCADE"), nullable=False
    )
    provider_product_id: Mapped[str] = mapped_column(String(160), nullable=False)
    region: Mapped[str | None] = mapped_column(String(120))
    match_alias: Mapped[str | None] = mapped_column(String(160))
    match_confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("1")
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class NutritionFoodPriceQuote(Base):
    __tablename__ = "nutrition_food_price_quotes"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    food_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_catalogue_foods.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    provider_code: Mapped[str] = mapped_column(
        ForeignKey("nutrition_price_providers.code", ondelete="RESTRICT"), nullable=False
    )
    provider_product_id: Mapped[str] = mapped_column(String(160), nullable=False)
    package_quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    package_unit: Mapped[str] = mapped_column(String(12), nullable=False)
    normal_price_irr: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    promotional_price_irr: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    normalized_normal_irr: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    normalized_promotional_irr: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_date: Mapped[date] = mapped_column(nullable=False)
    status: Mapped[PriceQuoteStatus] = mapped_column(
        enum_column(PriceQuoteStatus, "ck_nutrition_price_quote_status_values"), nullable=False
    )
    raw_quote: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class NutritionFoodPriceReference(Base):
    __tablename__ = "nutrition_food_price_references"
    food_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_catalogue_foods.id", ondelete="RESTRICT"), primary_key=True
    )
    canonical_unit: Mapped[str] = mapped_column(String(24), nullable=False)
    reference_price_toman: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    sample_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    confidence: Mapped[EstimateConfidence] = mapped_column(
        enum_column(EstimateConfidence, "ck_nutrition_price_ref_confidence_values"), nullable=False
    )
    status: Mapped[PriceReferenceStatus] = mapped_column(
        enum_column(PriceReferenceStatus, "ck_nutrition_price_ref_status_values"), nullable=False
    )
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NutritionFoodPriceHistory(Base):
    __tablename__ = "nutrition_food_price_history"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    food_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_catalogue_foods.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    canonical_unit: Mapped[str] = mapped_column(String(24), nullable=False)
    reference_price_toman: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    sample_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    confidence: Mapped[EstimateConfidence] = mapped_column(
        enum_column(EstimateConfidence, "ck_nutrition_price_history_confidence_values"),
        nullable=False,
    )
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_quote_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class NutritionFoodPriceUpdateRun(Base):
    __tablename__ = "nutrition_food_price_update_runs"
    __table_args__ = (
        UniqueConstraint("scheduled_for", name="uq_nutrition_price_run_scheduled_for"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[PriceUpdateRunStatus] = mapped_column(
        enum_column(PriceUpdateRunStatus, "ck_nutrition_price_run_status_values"), nullable=False
    )
    foods_attempted: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    foods_updated: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    foods_unchanged: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    foods_needing_review: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    provider_failures: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    details: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class NutritionFoodPriceReview(Base):
    __tablename__ = "nutrition_food_price_reviews"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_food_price_update_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    food_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_catalogue_foods.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    reason_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    candidate_reference_price_toman: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NutritionCookingEquipment(Base):
    __tablename__ = "nutrition_cooking_equipment"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_profiles.user_id", ondelete="CASCADE"), primary_key=True
    )
    equipment: Mapped[CookingEquipment] = mapped_column(
        enum_column(CookingEquipment, "ck_nutrition_cooking_equipment_values"), primary_key=True
    )


class NutritionFoodItem(Base):
    __tablename__ = "nutrition_food_items"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "kind", "normalized_name", name="uq_nutrition_food_items_user_kind_name"
        ),
        CheckConstraint(
            "char_length(btrim(name)) BETWEEN 1 AND 120", name="ck_nutrition_food_items_name"
        ),
        CheckConstraint(
            "details IS NULL OR char_length(details) <= 500", name="ck_nutrition_food_items_details"
        ),
        Index("ix_nutrition_food_items_kind_name", "kind", "normalized_name"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_profiles.user_id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[FoodItemKind] = mapped_column(
        enum_column(FoodItemKind, "ck_nutrition_food_items_kind_values"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False)
    details: Mapped[str | None] = mapped_column(String(500))


class NutritionPlannerPolicyVersion(Base):
    __tablename__ = "nutrition_planner_policy_versions"

    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    planner_version: Mapped[str] = mapped_column(String(64), nullable=False)
    meal_distribution_policy: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    portion_policy: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    scoring_policy: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    tolerance_policy: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NutritionPlanGeneration(Base):
    __tablename__ = "nutrition_plan_generations"
    __table_args__ = (Index("ix_nutrition_plan_generations_user_created", "user_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    estimate_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("nutrition_estimates.id", ondelete="RESTRICT")
    )
    safety_decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_safety_decisions.id", ondelete="RESTRICT"), nullable=False
    )
    outcome: Mapped[NutritionPlanGenerationOutcome] = mapped_column(
        enum_column(
            NutritionPlanGenerationOutcome,
            "ck_nutrition_plan_generation_outcome_values",
        ),
        nullable=False,
    )
    reason_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    warning_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    input_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    input_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    diagnostic_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    planner_policy_version: Mapped[str] = mapped_column(
        ForeignKey("nutrition_planner_policy_versions.version", ondelete="RESTRICT"),
        nullable=False,
    )
    planner_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class NutritionWeeklyPlan(Base):
    __tablename__ = "nutrition_weekly_plans"
    __table_args__ = (
        UniqueConstraint("user_id", "revision", name="uq_nutrition_weekly_plan_user_revision"),
        UniqueConstraint("generation_id", name="uq_nutrition_weekly_plan_generation"),
        CheckConstraint("revision > 0", name="ck_nutrition_weekly_plan_revision_positive"),
        Index("ix_nutrition_weekly_plans_user_created", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_profiles.user_id", ondelete="CASCADE"), nullable=False
    )
    generation_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_plan_generations.id", ondelete="RESTRICT"), nullable=False
    )
    estimate_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_estimates.id", ondelete="RESTRICT"), nullable=False
    )
    safety_decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_safety_decisions.id", ondelete="RESTRICT"), nullable=False
    )
    revision: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    lifecycle_status: Mapped[NutritionPlanLifecycleStatus] = mapped_column(
        enum_column(
            NutritionPlanLifecycleStatus,
            "ck_nutrition_weekly_plan_lifecycle_values",
        ),
        nullable=False,
    )
    is_user_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    start_date: Mapped[date] = mapped_column(nullable=False)
    planner_policy_version: Mapped[str] = mapped_column(
        ForeignKey("nutrition_planner_policy_versions.version", ondelete="RESTRICT"),
        nullable=False,
    )
    planner_version: Mapped[str] = mapped_column(String(64), nullable=False)
    scientific_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(64), nullable=False)
    food_data_manifest: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    input_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    price_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    repair_snapshot: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    warning_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    explanation_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    weekly_cost_irr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    weekly_budget_irr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    budget_status: Mapped[NutritionPlanBudgetStatus] = mapped_column(
        enum_column(NutritionPlanBudgetStatus, "ck_nutrition_weekly_plan_budget_values"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    days: Mapped[list["NutritionWeeklyPlanDay"]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="NutritionWeeklyPlanDay.day_index",
    )
    nutrients: Mapped[list["NutritionWeeklyPlanNutrient"]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="NutritionWeeklyPlanNutrient.nutrient_code",
    )
    review: Mapped["NutritionPlanPhysicianReview | None"] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )


class NutritionWeeklyPlanDay(Base):
    __tablename__ = "nutrition_weekly_plan_days"
    __table_args__ = (
        UniqueConstraint("plan_id", "day_index", name="uq_nutrition_weekly_plan_day"),
        CheckConstraint("day_index BETWEEN 0 AND 6", name="ck_nutrition_weekly_plan_day_index"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_weekly_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    day_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    plan_date: Mapped[date] = mapped_column(nullable=False)
    cost_irr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    nutrient_totals: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    meals: Mapped[list["NutritionWeeklyPlanMeal"]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="NutritionWeeklyPlanMeal.slot_role, NutritionWeeklyPlanMeal.slot_index",
    )


class NutritionWeeklyPlanMeal(Base):
    __tablename__ = "nutrition_weekly_plan_meals"
    __table_args__ = (
        UniqueConstraint(
            "day_id", "slot_role", "slot_index", name="uq_nutrition_weekly_plan_meal_slot"
        ),
        CheckConstraint("slot_index >= 0", name="ck_nutrition_weekly_plan_meal_slot_index"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    day_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_weekly_plan_days.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slot_role: Mapped[MealSlotRole] = mapped_column(
        enum_column(MealSlotRole, "ck_nutrition_weekly_plan_meal_role_values"), nullable=False
    )
    slot_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    target_distribution: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    nutrient_totals: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    cost_irr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    foods: Mapped[list["NutritionWeeklyPlanFood"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="NutritionWeeklyPlanFood.id"
    )


class NutritionWeeklyPlanFood(Base):
    __tablename__ = "nutrition_weekly_plan_foods"
    __table_args__ = (
        CheckConstraint("grams > 0", name="ck_nutrition_weekly_plan_food_grams_positive"),
        CheckConstraint("cost_irr >= 0", name="ck_nutrition_weekly_plan_food_cost_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    meal_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_weekly_plan_meals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    food_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_catalogue_foods.id", ondelete="RESTRICT"), nullable=False
    )
    food_slug: Mapped[str] = mapped_column(String(120), nullable=False)
    food_name_fa: Mapped[str] = mapped_column(String(160), nullable=False)
    food_name_en: Mapped[str] = mapped_column(String(160), nullable=False)
    grams: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    cost_irr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    nutrient_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    price_snapshot: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class NutritionWeeklyPlanNutrient(Base):
    __tablename__ = "nutrition_weekly_plan_nutrients"

    plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_weekly_plans.id", ondelete="CASCADE"), primary_key=True
    )
    nutrient_code: Mapped[str] = mapped_column(String(48), primary_key=True)
    unit: Mapped[str] = mapped_column(String(24), nullable=False)
    reference_kind: Mapped[str | None] = mapped_column(String(24))
    preferred_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    minimum_or_maximum_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    planned_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    difference_from_preferred: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    difference_from_limit: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    data_confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    explanation_codes: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class NutritionPlanPhysicianReview(Base):
    __tablename__ = "nutrition_plan_physician_reviews"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_weekly_plans.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[NutritionPlanReviewStatus] = mapped_column(
        enum_column(NutritionPlanReviewStatus, "ck_nutrition_plan_review_status_values"),
        nullable=False,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    physician_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_visible_notes: Mapped[str | None] = mapped_column(String(2000))


class NutritionPhysicianReview(Base):
    __tablename__ = "nutrition_physician_reviews"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"), nullable=False, index=True
    )
    safety_decision_id: Mapped[UUID] = mapped_column(
        ForeignKey("nutrition_safety_decisions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    mode: Mapped[PhysicianReviewMode] = mapped_column(
        enum_column(PhysicianReviewMode, "ck_nutrition_physician_reviews_mode_values"),
        nullable=False,
    )
    status: Mapped[PhysicianReviewStatus] = mapped_column(
        enum_column(PhysicianReviewStatus, "ck_nutrition_physician_reviews_status_values"),
        nullable=False,
    )
    reviewer_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    notes: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
