from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from app.exercises.enums import BodyRegion, Difficulty, Equipment, MediaType, MuscleGroup

SearchText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100),
]


class ExerciseFilters(BaseModel):
    body_region: BodyRegion | None = None
    primary_muscle: MuscleGroup | None = None
    equipment: Equipment | None = None
    difficulty: Difficulty | None = None
    search: SearchText | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=12, ge=1, le=50)


class ExerciseCategory(BaseModel):
    value: MuscleGroup
    name_en: str
    name_fa: str


class BodyRegionCategory(BaseModel):
    value: BodyRegion
    name_en: str
    name_fa: str


class ExerciseCategories(BaseModel):
    body_regions: list[BodyRegionCategory]
    upper_body: list[ExerciseCategory]
    lower_body: list[ExerciseCategory]
    core: list[ExerciseCategory]


class ExerciseSummary(BaseModel):
    id: UUID
    slug: str
    name_en: str
    name_fa: str
    body_region: BodyRegion
    primary_muscle: MuscleGroup
    secondary_muscles: list[MuscleGroup]
    equipment: list[Equipment]
    difficulty: Difficulty
    media_path: str
    media_type: MediaType


class ExerciseDetail(ExerciseSummary):
    instructions_en: list[str]
    instructions_fa: list[str]
    safety_notes_en: list[str]
    safety_notes_fa: list[str]
    media_source_url: str | None
    media_license: str | None
    media_attribution: str | None


class PaginatedExercises(BaseModel):
    items: list[ExerciseSummary]
    page: int
    page_size: int
    total: int
    total_pages: int
