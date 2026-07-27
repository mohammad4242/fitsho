from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import ValidationError

from app.admin.dependencies import require_admin
from app.admin.exceptions import DuplicateExerciseSlugError
from app.admin.media import MediaValidationError, StoredMedia, discard_media, store_upload
from app.admin.schemas import (
    AdminExerciseCreate,
    AdminExerciseDetail,
    AdminExerciseFilters,
    PaginatedAdminExercises,
)
from app.admin.service import create_admin_exercise, list_admin_exercises
from app.auth.cookies import require_trusted_origin
from app.auth.dependencies import AppSettings, DatabaseSession
from app.exercises.models import Exercise
from app.exercises.taxonomy import MUSCLES_BY_REGION

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


def _detail(exercise: Exercise) -> AdminExerciseDetail:
    return AdminExerciseDetail(
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
        instructions_en=exercise.instructions_en,
        instructions_fa=exercise.instructions_fa,
        safety_notes_en=exercise.safety_notes_en,
        safety_notes_fa=exercise.safety_notes_fa,
        media_path=exercise.media_path,
        media_type=exercise.media_type,
        media_source_url=exercise.media_source_url,
        media_license=exercise.media_license,
        media_attribution=exercise.media_attribution,
        is_active=exercise.is_active,
        created_at=exercise.created_at,
        updated_at=exercise.updated_at,
    )


def _validation_error(field: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=[
            {
                "type": "value_error",
                "loc": ["body", field],
                "msg": message,
            }
        ],
    )


def _parse_payload(raw_payload: str) -> AdminExerciseCreate:
    try:
        payload = AdminExerciseCreate.model_validate_json(raw_payload)
    except ValidationError as error:
        detail = [
            {
                "type": item["type"],
                "loc": ["body", *item["loc"]],
                "msg": item["msg"],
            }
            for item in error.errors()
        ]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=detail,
        ) from None

    allowed_muscles = MUSCLES_BY_REGION[payload.body_region]
    if payload.primary_muscle not in allowed_muscles:
        raise _validation_error(
            "primary_muscle",
            "Primary muscle must belong to the selected body region",
        )
    if any(muscle not in allowed_muscles for muscle in payload.secondary_muscles):
        raise _validation_error(
            "secondary_muscles",
            "Secondary muscles must belong to the selected body region",
        )
    if payload.primary_muscle in payload.secondary_muscles:
        raise _validation_error(
            "secondary_muscles",
            "Primary muscle cannot also be a secondary muscle",
        )
    return payload


@router.get("/exercises", response_model=PaginatedAdminExercises)
def read_admin_exercises(
    filters: Annotated[AdminExerciseFilters, Query()],
    db: DatabaseSession,
) -> PaginatedAdminExercises:
    exercises, total = list_admin_exercises(db, filters)
    return PaginatedAdminExercises(
        items=[_detail(exercise) for exercise in exercises],
        page=filters.page,
        page_size=filters.page_size,
        total=total,
        total_pages=(total + filters.page_size - 1) // filters.page_size,
    )


@router.post(
    "/exercises",
    response_model=AdminExerciseDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def create_exercise(
    payload: Annotated[str, Form()],
    db: DatabaseSession,
    settings: AppSettings,
    media: Annotated[UploadFile | None, File()] = None,
) -> AdminExerciseDetail:
    exercise_payload = _parse_payload(payload)
    stored_media: StoredMedia | None = None
    try:
        if media is not None:
            stored_media = store_upload(media, settings)
        exercise = create_admin_exercise(db, exercise_payload, stored_media)
    except MediaValidationError as error:
        raise _validation_error("media", str(error)) from None
    except DuplicateExerciseSlugError:
        if stored_media is not None:
            discard_media(stored_media)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Exercise slug already exists",
        ) from None
    except Exception:
        if stored_media is not None:
            discard_media(stored_media)
        raise
    return _detail(exercise)
