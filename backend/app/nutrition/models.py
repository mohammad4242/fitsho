from datetime import datetime, time
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
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
    DietaryPattern,
    FoodItemKind,
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
    individual_monthly_food_budget_irr: Mapped[int] = mapped_column(BigInteger, nullable=False)
    budget_style: Mapped[BudgetStyle] = mapped_column(
        enum_column(BudgetStyle, "ck_nutrition_profiles_budget_style_values"), nullable=False
    )
    meals_per_day: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    snacks_per_day: Mapped[int] = mapped_column(SmallInteger, nullable=False)
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
