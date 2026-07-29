from typing import Annotated
from uuid import UUID

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
from app.admin.service import (
    MediaAssetKey,
    create_admin_exercise,
    get_admin_exercise,
    list_admin_exercises,
    update_admin_exercise,
)
from app.auth.cookies import require_trusted_origin
from app.auth.dependencies import AppSettings, DatabaseSession
from app.exercises.enums import MediaPresentation, MediaRole, MediaType
from app.exercises.models import Exercise
from app.exercises.schemas import ExerciseMediaAssetDetail
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
        source=exercise.source,
        source_id=exercise.source_id,
        aliases_en=exercise.aliases_en,
        short_description_en=exercise.short_description_en,
        steps_en=exercise.steps_en,
        form_cues_en=exercise.form_cues_en,
        common_mistakes_en=exercise.common_mistakes_en,
        breathing_en=exercise.breathing_en,
        needs_review=exercise.needs_review,
        media_path=exercise.media_path,
        media_type=exercise.media_type,
        media_source_url=exercise.media_source_url,
        media_license=exercise.media_license,
        media_attribution=exercise.media_attribution,
        media_assets=[
            ExerciseMediaAssetDetail(
                presentation=asset.presentation,
                role=asset.role,
                sort_order=asset.sort_order,
                media_path=asset.media_path,
                media_type=asset.media_type,
                media_source_url=asset.media_source_url,
                media_license=asset.media_license,
                media_attribution=asset.media_attribution,
            )
            for asset in exercise.media_assets
        ],
        is_active=exercise.is_active,
        created_at=exercise.created_at,
        movement_pattern=exercise.movement_pattern,
        exercise_type=exercise.exercise_type,
        caution_tags=sorted(
            (item.caution_tag for item in exercise.caution_tag_items), key=lambda value: value.value
        ),
        is_programmable=exercise.is_programmable,
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
    if payload.primary_muscle in payload.secondary_muscles:
        raise _validation_error(
            "secondary_muscles",
            "Primary muscle cannot also be a secondary muscle",
        )
    return payload


def _variant_uploads(
    settings: AppSettings,
    uploads: dict[MediaAssetKey, UploadFile | None],
) -> dict[MediaAssetKey, StoredMedia]:
    stored: dict[MediaAssetKey, StoredMedia] = {}
    try:
        for key, upload in uploads.items():
            if upload is None:
                continue
            media = store_upload(upload, settings)
            expected_type = MediaType.VIDEO if key[1] is MediaRole.VIDEO else MediaType.IMAGE
            if media.media_type is not expected_type:
                discard_media(media)
                raise MediaValidationError("Media file type does not match its media role")
            stored[key] = media
    except Exception:
        for media in stored.values():
            discard_media(media)
        raise
    return stored


def _discard_media_assets(media_assets: dict[MediaAssetKey, StoredMedia]) -> None:
    for media in media_assets.values():
        discard_media(media)


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


@router.get("/exercises/{exercise_id}", response_model=AdminExerciseDetail)
def read_admin_exercise(
    exercise_id: UUID,
    db: DatabaseSession,
) -> AdminExerciseDetail:
    exercise = get_admin_exercise(db, exercise_id)
    if exercise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    return _detail(exercise)


@router.patch(
    "/exercises/{exercise_id}",
    response_model=AdminExerciseDetail,
    dependencies=[Depends(require_trusted_origin)],
)
def update_exercise(
    exercise_id: UUID,
    payload: Annotated[str, Form()],
    db: DatabaseSession,
    settings: AppSettings,
    media: Annotated[UploadFile | None, File()] = None,
    media_male_video: Annotated[UploadFile | None, File()] = None,
    media_female_video: Annotated[UploadFile | None, File()] = None,
    media_male_thumbnail: Annotated[UploadFile | None, File()] = None,
    media_female_thumbnail: Annotated[UploadFile | None, File()] = None,
) -> AdminExerciseDetail:
    exercise_payload = _parse_payload(payload)
    stored_media: StoredMedia | None = None
    stored_media_assets: dict[MediaAssetKey, StoredMedia] = {}
    try:
        if media is not None:
            stored_media = store_upload(media, settings)
        stored_media_assets = _variant_uploads(
            settings,
            {
                (MediaPresentation.MALE, MediaRole.VIDEO): media_male_video,
                (MediaPresentation.FEMALE, MediaRole.VIDEO): media_female_video,
                (MediaPresentation.MALE, MediaRole.THUMBNAIL): media_male_thumbnail,
                (MediaPresentation.FEMALE, MediaRole.THUMBNAIL): media_female_thumbnail,
            },
        )
        exercise = update_admin_exercise(
            db,
            exercise_id,
            exercise_payload,
            stored_media,
            stored_media_assets,
        )
        if exercise is None:
            if stored_media is not None:
                discard_media(stored_media)
            _discard_media_assets(stored_media_assets)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Exercise not found",
            )
    except MediaValidationError as error:
        if stored_media is not None:
            discard_media(stored_media)
        _discard_media_assets(stored_media_assets)
        raise _validation_error("media", str(error)) from None
    except ValueError as error:
        if stored_media is not None:
            discard_media(stored_media)
        _discard_media_assets(stored_media_assets)
        raise _validation_error("media_assets", str(error)) from None
    except DuplicateExerciseSlugError:
        if stored_media is not None:
            discard_media(stored_media)
        _discard_media_assets(stored_media_assets)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Exercise slug already exists",
        ) from None
    except HTTPException:
        raise
    except Exception:
        if stored_media is not None:
            discard_media(stored_media)
        _discard_media_assets(stored_media_assets)
        raise
    return _detail(exercise)


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
    media_male_video: Annotated[UploadFile | None, File()] = None,
    media_female_video: Annotated[UploadFile | None, File()] = None,
    media_male_thumbnail: Annotated[UploadFile | None, File()] = None,
    media_female_thumbnail: Annotated[UploadFile | None, File()] = None,
) -> AdminExerciseDetail:
    exercise_payload = _parse_payload(payload)
    stored_media: StoredMedia | None = None
    stored_media_assets: dict[MediaAssetKey, StoredMedia] = {}
    try:
        if media is not None:
            stored_media = store_upload(media, settings)
        stored_media_assets = _variant_uploads(
            settings,
            {
                (MediaPresentation.MALE, MediaRole.VIDEO): media_male_video,
                (MediaPresentation.FEMALE, MediaRole.VIDEO): media_female_video,
                (MediaPresentation.MALE, MediaRole.THUMBNAIL): media_male_thumbnail,
                (MediaPresentation.FEMALE, MediaRole.THUMBNAIL): media_female_thumbnail,
            },
        )
        exercise = create_admin_exercise(
            db,
            exercise_payload,
            stored_media,
            stored_media_assets,
        )
    except MediaValidationError as error:
        if stored_media is not None:
            discard_media(stored_media)
        _discard_media_assets(stored_media_assets)
        raise _validation_error("media", str(error)) from None
    except ValueError as error:
        if stored_media is not None:
            discard_media(stored_media)
        _discard_media_assets(stored_media_assets)
        raise _validation_error("media_assets", str(error)) from None
    except DuplicateExerciseSlugError:
        if stored_media is not None:
            discard_media(stored_media)
        _discard_media_assets(stored_media_assets)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Exercise slug already exists",
        ) from None
    except Exception:
        if stored_media is not None:
            discard_media(stored_media)
        _discard_media_assets(stored_media_assets)
        raise
    return _detail(exercise)
