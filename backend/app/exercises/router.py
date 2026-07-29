from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import DatabaseSession
from app.exercises.dependencies import require_completed_profile
from app.exercises.enums import BodyRegion, MuscleGroup
from app.exercises.models import Exercise
from app.exercises.schemas import (
    BodyRegionCategory,
    ExerciseCategories,
    ExerciseCategory,
    ExerciseDetail,
    ExerciseFilters,
    ExerciseMediaAssetDetail,
    ExerciseSummary,
    PaginatedExercises,
)
from app.exercises.service import get_active_exercise_by_slug, list_exercises

router = APIRouter(
    prefix="/api/v1",
    tags=["exercises"],
    dependencies=[Depends(require_completed_profile)],
)

BODY_REGION_CATEGORIES = (
    (BodyRegion.UPPER_BODY, "Upper Body", "بالاتنه"),
    (BodyRegion.LOWER_BODY, "Lower Body", "پایین‌تنه"),
    (BodyRegion.CORE, "Core", "میان‌تنه"),
)
UPPER_BODY_CATEGORIES = (
    (MuscleGroup.CHEST, "Chest", "سینه"),
    (MuscleGroup.BACK, "Back", "پشت و زیر بغل"),
    (MuscleGroup.SHOULDERS, "Shoulders", "سرشانه"),
    (MuscleGroup.BICEPS, "Biceps", "جلو بازو"),
    (MuscleGroup.TRICEPS, "Triceps", "پشت بازو"),
    (MuscleGroup.TRAPS, "Traps", "کول"),
)
LOWER_BODY_CATEGORIES = (
    (MuscleGroup.GLUTES, "Glutes", "باسن"),
    (MuscleGroup.QUADRICEPS, "Quadriceps", "جلو پا"),
    (MuscleGroup.HAMSTRINGS, "Hamstrings", "پشت پا"),
    (MuscleGroup.ADDUCTORS, "Adductors", "داخل پا"),
    (MuscleGroup.CALVES, "Calves", "ساق"),
)
CORE_CATEGORIES = (
    (MuscleGroup.ABS, "Abs", "شکم"),
    (MuscleGroup.OBLIQUES, "Obliques", "پهلو"),
    (MuscleGroup.LOWER_BACK, "Lower Back", "فیله"),
)


def _category_items(
    values: tuple[tuple[MuscleGroup, str, str], ...],
) -> list[ExerciseCategory]:
    return [
        ExerciseCategory(value=value, name_en=name_en, name_fa=name_fa)
        for value, name_en, name_fa in values
    ]


def _body_region_items() -> list[BodyRegionCategory]:
    return [
        BodyRegionCategory(value=value, name_en=name_en, name_fa=name_fa)
        for value, name_en, name_fa in BODY_REGION_CATEGORIES
    ]


def _summary(exercise: Exercise) -> ExerciseSummary:
    return ExerciseSummary(
        id=exercise.id,
        slug=exercise.slug,
        name_en=exercise.name_en,
        name_fa=exercise.name_fa,
        body_region=exercise.body_region,
        primary_muscle=exercise.primary_muscle,
        secondary_muscles=sorted(
            (item.muscle for item in exercise.secondary_muscles),
            key=lambda value: value.value,
        ),
        equipment=sorted(
            (item.equipment for item in exercise.equipment_items),
            key=lambda value: value.value,
        ),
        difficulty=exercise.difficulty,
        media_path=exercise.media_path,
        media_type=exercise.media_type,
    )


def _detail(exercise: Exercise) -> ExerciseDetail:
    summary = _summary(exercise)
    return ExerciseDetail(
        **summary.model_dump(),
        instructions_en=exercise.instructions_en,
        instructions_fa=exercise.instructions_fa,
        safety_notes_en=exercise.safety_notes_en,
        safety_notes_fa=exercise.safety_notes_fa,
        media_source_url=exercise.media_source_url,
        media_license=exercise.media_license,
        media_attribution=exercise.media_attribution,
        media_assets=[
            ExerciseMediaAssetDetail(
                presentation=asset.presentation,
                role=asset.role,
                media_path=asset.media_path,
                media_type=asset.media_type,
                media_source_url=asset.media_source_url,
                media_license=asset.media_license,
                media_attribution=asset.media_attribution,
            )
            for asset in exercise.media_assets
        ],
    )


@router.get("/exercise-categories", response_model=ExerciseCategories)
def categories() -> ExerciseCategories:
    return ExerciseCategories(
        body_regions=_body_region_items(),
        upper_body=_category_items(UPPER_BODY_CATEGORIES),
        lower_body=_category_items(LOWER_BODY_CATEGORIES),
        core=_category_items(CORE_CATEGORIES),
    )


@router.get("/exercises", response_model=PaginatedExercises)
def read_exercises(
    filters: Annotated[ExerciseFilters, Query()],
    db: DatabaseSession,
) -> PaginatedExercises:
    exercises, total = list_exercises(db, filters)
    total_pages = (total + filters.page_size - 1) // filters.page_size
    return PaginatedExercises(
        items=[_summary(exercise) for exercise in exercises],
        page=filters.page,
        page_size=filters.page_size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/exercises/{slug}", response_model=ExerciseDetail)
def read_exercise(slug: str, db: DatabaseSession) -> ExerciseDetail:
    exercise = get_active_exercise_by_slug(db, slug)
    if exercise is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found",
        )
    return _detail(exercise)
