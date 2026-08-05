from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.profile.enums import (
    ExperienceLevel,
    FitnessGoal,
    HomeTrainingSetup,
    ProductMode,
    Sex,
    TrainingCaution,
    TrainingLocation,
    WorkoutGenerationMethod,
)


class UserProfile(Base):
    __tablename__ = "user_profiles"
    __table_args__ = (
        CheckConstraint(
            "char_length(btrim(display_name)) BETWEEN 2 AND 80",
            name="ck_user_profiles_display_name_length",
        ),
        CheckConstraint("height_cm BETWEEN 120 AND 230", name="ck_user_profiles_height_cm_range"),
        CheckConstraint(
            "training_days_per_week BETWEEN 2 AND 6",
            name="ck_user_profiles_training_days_range",
        ),
        CheckConstraint(
            "physical_limitations IS NULL OR char_length(physical_limitations) <= 1000",
            name="ck_user_profiles_limitations_length",
        ),
        CheckConstraint(
            "session_duration_minutes IN (30, 45, 60, 75, 90)",
            name="ck_user_profiles_session_duration_values",
        ),
        CheckConstraint(
            "plan_duration_weeks IN (4, 6, 8)",
            name="ck_user_profiles_plan_duration_weeks_values",
        ),
        CheckConstraint(
            "(training_location = 'home' AND home_training_setup IS NOT NULL) OR "
            "(training_location = 'gym' AND home_training_setup IS NULL)",
            name="ck_user_profiles_training_setup_consistency",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    product_mode: Mapped[ProductMode] = mapped_column(
        Enum(ProductMode, native_enum=False, create_constraint=True, validate_strings=True,
             values_callable=lambda members: [member.value for member in members],
             name="ck_user_profiles_product_mode_values"),
        default=ProductMode.TRAINING,
        nullable=False,
    )
    display_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sex: Mapped[Sex | None] = mapped_column(
        Enum(
            Sex,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda members: [member.value for member in members],
            name="ck_user_profiles_sex_values",
        ),
        nullable=True,
    )
    height_cm: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    fitness_goal: Mapped[FitnessGoal | None] = mapped_column(
        Enum(
            FitnessGoal,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda members: [member.value for member in members],
            name="ck_user_profiles_fitness_goal_values",
        ),
        nullable=True,
    )
    experience_level: Mapped[ExperienceLevel | None] = mapped_column(
        Enum(
            ExperienceLevel,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda members: [member.value for member in members],
            name="ck_user_profiles_experience_level_values",
        ),
        nullable=True,
    )
    training_days_per_week: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    training_location: Mapped[TrainingLocation | None] = mapped_column(
        Enum(
            TrainingLocation,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda members: [member.value for member in members],
            name="ck_user_profiles_training_location_values",
        ),
        nullable=True,
    )
    home_training_setup: Mapped[HomeTrainingSetup | None] = mapped_column(
        Enum(
            HomeTrainingSetup,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda members: [member.value for member in members],
            name="ck_user_profiles_home_training_setup_values",
        ),
        nullable=True,
    )
    session_duration_minutes: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    physical_limitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan_duration_weeks: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    workout_generation_method: Mapped[WorkoutGenerationMethod | None] = mapped_column(
        Enum(
            WorkoutGenerationMethod,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda members: [member.value for member in members],
            name="ck_user_profiles_workout_generation_method_values",
        ),
        nullable=True,
    )
    training_caution_items: Mapped[list["UserProfileTrainingCaution"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan", passive_deletes=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UserProfileTrainingCaution(Base):
    __tablename__ = "user_profile_training_cautions"
    __table_args__ = (Index("ix_user_profile_training_cautions_caution", "caution"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"), primary_key=True
    )
    caution: Mapped[TrainingCaution] = mapped_column(
        Enum(
            TrainingCaution,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda members: [member.value for member in members],
            name="ck_user_profile_training_cautions_values",
        ),
        primary_key=True,
    )
    profile: Mapped[UserProfile] = relationship(back_populates="training_caution_items")


class BodyMeasurement(Base):
    __tablename__ = "body_measurements"
    __table_args__ = (
        CheckConstraint(
            "weight_kg BETWEEN 35 AND 300",
            name="ck_body_measurements_weight_kg_range",
        ),
        CheckConstraint(
            "shoulder_circumference_cm IS NULL OR shoulder_circumference_cm BETWEEN 40 AND 250",
            name="ck_body_measurements_shoulder_circumference_range",
        ),
        CheckConstraint(
            "waist_circumference_cm IS NULL OR waist_circumference_cm BETWEEN 40 AND 250",
            name="ck_body_measurements_waist_circumference_range",
        ),
        CheckConstraint(
            "hip_circumference_cm IS NULL OR hip_circumference_cm BETWEEN 40 AND 250",
            name="ck_body_measurements_hip_circumference_range",
        ),
        Index("ix_body_measurements_user_id_measured_at", "user_id", "measured_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    shoulder_circumference_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    waist_circumference_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    hip_circumference_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
