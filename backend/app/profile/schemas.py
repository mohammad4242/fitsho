from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.profile.enums import ExperienceLevel, FitnessGoal, Sex


def calculate_age(birth_date: date, today: date) -> int:
    return (
        today.year
        - birth_date.year
        - ((today.month, today.day) < (birth_date.month, birth_date.day))
    )


class ProfileCreate(BaseModel):
    display_name: str = Field(min_length=2, max_length=80)
    birth_date: date
    sex: Sex
    height_cm: int = Field(ge=100, le=250)
    current_weight_kg: Decimal = Field(
        ge=Decimal("20"),
        le=Decimal("500"),
        max_digits=5,
        decimal_places=2,
    )
    fitness_goal: FitnessGoal
    experience_level: ExperienceLevel
    training_days_per_week: int = Field(ge=1, le=7)
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

    @field_validator("birth_date")
    @classmethod
    def validate_age(cls, birth_date: date) -> date:
        age = calculate_age(birth_date, date.today())
        if not 18 <= age <= 100:
            raise ValueError("Age must be between 18 and 100 years")
        return birth_date


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    birth_date: date | None = None
    sex: Sex | None = None
    height_cm: int | None = Field(default=None, ge=100, le=250)
    current_weight_kg: Decimal | None = Field(
        default=None,
        ge=Decimal("20"),
        le=Decimal("500"),
        max_digits=5,
        decimal_places=2,
    )
    fitness_goal: FitnessGoal | None = None
    experience_level: ExperienceLevel | None = None
    training_days_per_week: int | None = Field(default=None, ge=1, le=7)
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

    @field_validator("birth_date")
    @classmethod
    def validate_age(cls, birth_date: date | None) -> date | None:
        if birth_date is None:
            return None

        age = calculate_age(birth_date, date.today())
        if not 18 <= age <= 100:
            raise ValueError("Age must be between 18 and 100 years")
        return birth_date

    @model_validator(mode="after")
    def validate_supplied_fields(self) -> "ProfileUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one profile field is required")

        required_fields = self.model_fields_set - {"physical_limitations"}
        if any(getattr(self, field_name) is None for field_name in required_fields):
            raise ValueError("Profile fields cannot be null")
        return self


class ProfileResponse(BaseModel):
    user_id: UUID
    display_name: str
    birth_date: date
    sex: Sex
    height_cm: int
    current_weight_kg: float
    weight_measured_at: datetime
    fitness_goal: FitnessGoal
    experience_level: ExperienceLevel
    training_days_per_week: int
    physical_limitations: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
