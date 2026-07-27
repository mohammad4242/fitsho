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
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.profile.enums import (
    ExperienceLevel,
    FitnessGoal,
    HomeTrainingSetup,
    Sex,
    TrainingLocation,
)


class UserProfile(Base):
    __tablename__ = "user_profiles"
    __table_args__ = (
        CheckConstraint(
            "char_length(btrim(display_name)) BETWEEN 2 AND 80",
            name="ck_user_profiles_display_name_length",
        ),
        CheckConstraint("height_cm BETWEEN 100 AND 250", name="ck_user_profiles_height_cm_range"),
        CheckConstraint(
            "training_days_per_week BETWEEN 1 AND 7",
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
            "(training_location = 'home' AND home_training_setup IS NOT NULL) OR "
            "(training_location = 'gym' AND home_training_setup IS NULL)",
            name="ck_user_profiles_training_setup_consistency",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    sex: Mapped[Sex] = mapped_column(
        Enum(
            Sex,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda members: [member.value for member in members],
            name="ck_user_profiles_sex_values",
        ),
        nullable=False,
    )
    height_cm: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    fitness_goal: Mapped[FitnessGoal] = mapped_column(
        Enum(
            FitnessGoal,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda members: [member.value for member in members],
            name="ck_user_profiles_fitness_goal_values",
        ),
        nullable=False,
    )
    experience_level: Mapped[ExperienceLevel] = mapped_column(
        Enum(
            ExperienceLevel,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda members: [member.value for member in members],
            name="ck_user_profiles_experience_level_values",
        ),
        nullable=False,
    )
    training_days_per_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    training_location: Mapped[TrainingLocation] = mapped_column(
        Enum(
            TrainingLocation,
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda members: [member.value for member in members],
            name="ck_user_profiles_training_location_values",
        ),
        nullable=False,
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
    session_duration_minutes: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
    )
    physical_limitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class BodyMeasurement(Base):
    __tablename__ = "body_measurements"
    __table_args__ = (
        CheckConstraint(
            "weight_kg BETWEEN 20 AND 500",
            name="ck_body_measurements_weight_kg_range",
        ),
        Index("ix_body_measurements_user_id_measured_at", "user_id", "measured_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
