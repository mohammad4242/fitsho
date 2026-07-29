from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.exercises.enums import (
    BodyRegion,
    Difficulty,
    Equipment,
    ExerciseCautionTag,
    ExerciseType,
    MovementPattern,
    MuscleGroup,
)
from app.exercises.schemas import ExerciseDetail

Slug = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=120,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    ),
]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]
TextItem = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
OptionalMetadata = Annotated[
    str | None,
    StringConstraints(strip_whitespace=True, max_length=500),
]


class AdminExerciseFilters(BaseModel):
    search: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
    ] = None
    is_active: bool | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class AdminExerciseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: Slug
    name_en: Name
    name_fa: Name
    body_region: BodyRegion
    primary_muscle: MuscleGroup
    secondary_muscles: list[MuscleGroup] = Field(default_factory=list)
    equipment: list[Equipment] = Field(min_length=1)
    difficulty: Difficulty
    instructions_en: list[TextItem] = Field(min_length=3, max_length=6)
    instructions_fa: list[TextItem] = Field(min_length=3, max_length=6)
    safety_notes_en: list[TextItem] = Field(min_length=1)
    movement_pattern: MovementPattern = MovementPattern.OTHER
    exercise_type: ExerciseType = ExerciseType.OTHER
    caution_tags: list[ExerciseCautionTag] = Field(default_factory=list)
    is_programmable: bool = False
    safety_notes_fa: list[TextItem] = Field(min_length=1)
    is_active: bool = True
    media_source_url: OptionalMetadata = None
    media_license: Annotated[
        str | None,
        StringConstraints(strip_whitespace=True, max_length=120),
    ] = None
    media_attribution: OptionalMetadata = None


class AdminExerciseDetail(ExerciseDetail):
    is_active: bool
    created_at: datetime
    updated_at: datetime

    movement_pattern: MovementPattern
    exercise_type: ExerciseType
    caution_tags: list[ExerciseCautionTag]
    is_programmable: bool


class PaginatedAdminExercises(BaseModel):
    items: list[AdminExerciseDetail]
    page: int
    page_size: int
    total: int
    total_pages: int
