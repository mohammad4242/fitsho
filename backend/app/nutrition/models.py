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
    MainMealCountBucket,
    MealPreparationPreference,
    MedicalConditionCode,
    MetabolicBasis,
    MicronutrientAggregationWindow,
    MicronutrientReferenceKind,
    MicronutrientSex,
    MicronutrientUpperLimitScope,
    NutritionEstimateStatus,
    NutritionOnboardingStatus,
    NutritionPlanStyle,
    NutritionTargetMetric,
    PhysicianReviewMode,
    PhysicianReviewStatus,
    PreferredVariety,
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
