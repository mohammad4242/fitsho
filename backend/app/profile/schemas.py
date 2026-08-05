from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from app.profile.enums import (
    ExperienceLevel,
    FitnessGoal,
    HomeTrainingSetup,
    ProductMode,
    ProfileCompletionState,
    Sex,
    TrainingCaution,
    TrainingLocation,
    WorkoutGenerationMethod,
)

SessionDurationMinutes = Literal[30, 45, 60, 75, 90]
PlanDurationWeeks = Literal[4, 6, 8]
CircumferenceCm = Decimal


def calculate_age(birth_date: date, today: date) -> int:
    return (
        today.year
        - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day))
    )


def validate_supported_age(birth_date: date) -> date:
    age = calculate_age(birth_date, date.today())
    if age < 18:
        raise PydanticCustomError("AGE_NOT_SUPPORTED", "Age is not supported")
    if age > 100:
        raise PydanticCustomError("AGE_OUT_OF_RANGE", "Age is outside the supported range")
    return birth_date


class ProfileCreate(BaseModel):
    display_name: str = Field(min_length=2, max_length=80)
    birth_date: date
    sex: Sex
    height_cm: int = Field(ge=120, le=230)
    current_weight_kg: Decimal = Field(
        ge=Decimal("35"),
        le=Decimal("300"),
        max_digits=5,
        decimal_places=2,
    )
    shoulder_circumference_cm: CircumferenceCm | None = Field(
        default=None, ge=Decimal("40"), le=Decimal("250"), max_digits=5, decimal_places=2
    )
    waist_circumference_cm: CircumferenceCm | None = Field(
        default=None, ge=Decimal("40"), le=Decimal("250"), max_digits=5, decimal_places=2
    )
    hip_circumference_cm: CircumferenceCm | None = Field(
        default=None, ge=Decimal("40"), le=Decimal("250"), max_digits=5, decimal_places=2
    )
    fitness_goal: FitnessGoal
    experience_level: ExperienceLevel
    training_days_per_week: int = Field(ge=2, le=6)
    training_location: TrainingLocation
    home_training_setup: HomeTrainingSetup | None = None
    training_cautions: list[TrainingCaution] = Field(default_factory=list)
    plan_duration_weeks: PlanDurationWeeks = 4
    workout_generation_method: WorkoutGenerationMethod = WorkoutGenerationMethod.FITSHO_COACH
    session_duration_minutes: SessionDurationMinutes
    physical_limitations: str | None = Field(default=None, max_length=1000)

    @field_validator("display_name", "physical_limitations", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value

        normalized_value = value.strip()
        if normalized_value == "" and value is not None:
            return None
        return normalized_value

    @field_validator("training_cautions")
    @classmethod
    def validate_unique_training_cautions(
        cls, cautions: list[TrainingCaution]
    ) -> list[TrainingCaution]:
        if len(cautions) != len(set(cautions)):
            raise ValueError("Training cautions must be unique")
        return cautions

    @field_validator("birth_date")
    @classmethod
    def validate_age(cls, birth_date: date) -> date:
        return validate_supported_age(birth_date)

    @model_validator(mode="after")
    def normalize_workout_setup(self) -> "ProfileCreate":
        if self.training_location == TrainingLocation.GYM:
            self.home_training_setup = None
        elif self.home_training_setup is None:
            raise ValueError("Home training setup is required for home training")
        return self


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    birth_date: date | None = None
    sex: Sex | None = None
    height_cm: int | None = Field(default=None, ge=120, le=230)
    current_weight_kg: Decimal | None = Field(
        default=None,
        ge=Decimal("35"),
        le=Decimal("300"),
        max_digits=5,
        decimal_places=2,
    )
    shoulder_circumference_cm: CircumferenceCm | None = Field(
        default=None, ge=Decimal("40"), le=Decimal("250"), max_digits=5, decimal_places=2
    )
    waist_circumference_cm: CircumferenceCm | None = Field(
        default=None, ge=Decimal("40"), le=Decimal("250"), max_digits=5, decimal_places=2
    )
    hip_circumference_cm: CircumferenceCm | None = Field(
        default=None, ge=Decimal("40"), le=Decimal("250"), max_digits=5, decimal_places=2
    )
    fitness_goal: FitnessGoal | None = None
    experience_level: ExperienceLevel | None = None
    training_days_per_week: int | None = Field(default=None, ge=2, le=6)
    training_location: TrainingLocation | None = None
    home_training_setup: HomeTrainingSetup | None = None
    training_cautions: list[TrainingCaution] | None = None
    plan_duration_weeks: PlanDurationWeeks | None = None
    workout_generation_method: WorkoutGenerationMethod | None = None
    session_duration_minutes: SessionDurationMinutes | None = None
    physical_limitations: str | None = Field(default=None, max_length=1000)

    @field_validator("display_name", "physical_limitations", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value

        normalized_value = value.strip()
        if normalized_value == "":
            return None
        return normalized_value

    @field_validator("training_cautions")
    @classmethod
    def validate_unique_training_cautions(
        cls, cautions: list[TrainingCaution] | None
    ) -> list[TrainingCaution] | None:
        if cautions is not None and len(cautions) != len(set(cautions)):
            raise ValueError("Training cautions must be unique")
        return cautions

    @field_validator("birth_date")
    @classmethod
    def validate_age(cls, birth_date: date | None) -> date | None:
        if birth_date is None:
            return None

        return validate_supported_age(birth_date)

    @model_validator(mode="after")
    def validate_supplied_fields(self) -> "ProfileUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one profile field is required")

        required_fields = self.model_fields_set - {
            "home_training_setup",
            "physical_limitations",
            "shoulder_circumference_cm",
            "waist_circumference_cm",
            "hip_circumference_cm",
        }
        if any(getattr(self, field_name) is None for field_name in required_fields):
            raise ValueError("Profile fields cannot be null")
        if self.training_location == TrainingLocation.GYM:
            self.home_training_setup = None
        elif self.training_location == TrainingLocation.HOME and self.home_training_setup is None:
            raise ValueError("Home training setup is required for home training")
        return self


class ProfileResponse(BaseModel):
    user_id: UUID
    display_name: str
    birth_date: date
    sex: Sex
    height_cm: int
    current_weight_kg: float
    weight_measured_at: datetime
    shoulder_circumference_cm: float | None
    waist_circumference_cm: float | None
    hip_circumference_cm: float | None
    circumferences_measured_at: datetime | None
    fitness_goal: FitnessGoal
    experience_level: ExperienceLevel
    training_days_per_week: int
    physical_limitations: str | None
    created_at: datetime
    updated_at: datetime
    training_location: TrainingLocation
    home_training_setup: HomeTrainingSetup | None
    training_cautions: list[TrainingCaution]
    plan_duration_weeks: PlanDurationWeeks
    workout_generation_method: WorkoutGenerationMethod
    session_duration_minutes: SessionDurationMinutes

    model_config = ConfigDict(from_attributes=True)


class ProductModeSelection(BaseModel):
    product_mode: ProductMode


class SharedProfileUpsert(BaseModel):
    display_name: str = Field(min_length=2, max_length=80)
    birth_date: date
    sex: Sex
    height_cm: int = Field(ge=120, le=230)
    current_weight_kg: Decimal = Field(
        ge=Decimal("35"),
        le=Decimal("300"),
        max_digits=5,
        decimal_places=2,
    )
    fitness_goal: FitnessGoal

    @field_validator("display_name", mode="before")
    @classmethod
    def normalize_display_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class SharedProfileResponse(BaseModel):
    user_id: UUID
    product_mode: ProductMode
    display_name: str
    birth_date: date
    sex: Sex
    height_cm: int
    current_weight_kg: float
    weight_measured_at: datetime
    fitness_goal: FitnessGoal


class ProfileStatusResponse(BaseModel):
    user_id: UUID
    product_mode: ProductMode | None
    completion_state: ProfileCompletionState
