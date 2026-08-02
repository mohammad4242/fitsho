from typing import Annotated
from uuid import UUID

import httpx
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from pydantic import ValidationError

from app.admin.ai_models import (
    check_ai_model,
    create_ai_model,
    get_ai_model,
    list_ai_model_test_runs,
    list_ai_models,
    list_generation_failures,
    sync_zen_models,
    update_ai_model,
    update_ai_routing,
)
from app.admin.dependencies import require_admin
from app.admin.exceptions import DuplicateExerciseSlugError
from app.admin.media import MediaValidationError, StoredMedia, discard_media, store_upload
from app.admin.schemas import (
    AdminAiGenerationFailure,
    AdminAiModelCheckResponse,
    AdminAiModelCreate,
    AdminAiModelDetail,
    AdminAiModelsResponse,
    AdminAiModelSyncResponse,
    AdminAiModelTestRun,
    AdminAiModelUpdate,
    AdminAiRoutingDetail,
    AdminAiRoutingUpdate,
    AdminExerciseCreate,
    AdminExerciseDetail,
    AdminExerciseFilters,
    AdminTrainingProgramTemplate,
    AdminTrainingProgramTemplatesResponse,
    AdminTrainingTemplateDay,
    AdminTrainingTemplateExercise,
    AdminTrainingTemplateSlot,
    PaginatedAdminExercises,
)
from app.admin.service import (
    MediaAssetKey,
    create_admin_exercise,
    get_admin_exercise,
    list_admin_exercises,
    update_admin_exercise,
)
from app.ai.models import AiModel, AiModelTestRun, AiRoutingSettings
from app.auth.cookies import require_trusted_origin
from app.auth.dependencies import AppSettings, DatabaseSession
from app.exercises.enums import MediaPresentation, MediaRole, MediaType
from app.exercises.models import Exercise
from app.exercises.schemas import ExerciseMediaAssetDetail
from app.exercises.taxonomy import MUSCLES_BY_REGION
from app.training_templates.models import TrainingProgramTemplate
from app.training_templates.service import list_training_program_templates
from app.workouts.models import WorkoutPlanGeneration

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


def _ai_model_detail(model: AiModel) -> AdminAiModelDetail:
    return AdminAiModelDetail(
        id=model.id,
        model_id=model.model_id,
        display_name=model.display_name,
        api_kind=model.api_kind,
        billing_class=model.billing_class,
        is_enabled=model.is_enabled,
        priority=model.priority,
        is_custom=model.is_custom,
        classification_required=model.classification_required,
        last_synced_at=model.last_synced_at,
        last_checked_at=model.last_checked_at,
        last_error_code=model.last_error_code,
        last_error_message=model.last_error_message,
    )


def _ai_routing_detail(settings: AiRoutingSettings) -> AdminAiRoutingDetail:
    return AdminAiRoutingDetail(mode=settings.mode, manual_model_id=settings.manual_model_id)


def _ai_model_test_run_detail(run: AiModelTestRun) -> AdminAiModelTestRun:
    return AdminAiModelTestRun(
        id=run.id,
        model_id=run.model_id,
        outcome=run.outcome,
        error_code=run.error_code,
        safe_error_message=run.safe_error_message,
        provider_status_code=run.provider_status_code,
        provider_error_type=run.provider_error_type,
        provider_error_message=run.provider_error_message,
        created_at=run.created_at,
    )


def _ai_generation_failure_detail(generation: WorkoutPlanGeneration) -> AdminAiGenerationFailure:
    diagnostics = generation.validation_diagnostics
    if diagnostics is not None and any("errors" in diagnostic for diagnostic in diagnostics):
        normalized_diagnostics: list[dict[str, object]] = []
        for diagnostic in diagnostics:
            legacy_errors = diagnostic.get("errors")
            if not isinstance(legacy_errors, list):
                normalized_diagnostics.append(diagnostic)
                continue
            normalized_diagnostics.append(
                {
                    "model_id": generation.model_id,
                    "phase": "initial",
                    "problems": [
                        {
                            "code": error,
                            "message": "Deterministic program validation rejected this generation.",
                        }
                        for error in legacy_errors
                        if isinstance(error, str)
                    ],
                }
            )
        diagnostics = normalized_diagnostics
    return AdminAiGenerationFailure(
        id=generation.id,
        model_id=generation.model_id,
        created_at=generation.created_at,
        completed_at=generation.completed_at,
        error_code=generation.error_code,
        safe_error_message=generation.safe_error_message,
        validation_diagnostics=diagnostics,
    )


def _training_template_detail(template: TrainingProgramTemplate) -> AdminTrainingProgramTemplate:
    return AdminTrainingProgramTemplate(
        id=template.id,
        slug=template.slug,
        name_en=template.name_en,
        name_fa=template.name_fa,
        description_en=template.description_en,
        description_fa=template.description_fa,
        days_per_week=template.days_per_week,
        training_level=template.training_level,
        fitness_goal=template.fitness_goal,
        focus_tags=template.focus_tags,
        intensity_methods=template.intensity_methods,
        programming_rationale=template.programming_rationale,
        source_name=template.source_name,
        source_url=template.source_url,
        days=[
            AdminTrainingTemplateDay(
                id=day.id,
                day_number=day.day_number,
                title_en=day.title_en,
                title_fa=day.title_fa,
                direct_target_muscles=day.direct_target_muscles,
                slots=[
                    AdminTrainingTemplateSlot(
                        id=slot.id,
                        slot_order=slot.slot_order,
                        exercise_slug_hint=slot.exercise_slug_hint,
                        placeholder_name_en=slot.placeholder_name_en,
                        placeholder_name_fa=slot.placeholder_name_fa,
                        target_muscles=slot.target_muscles,
                        movement_pattern=slot.movement_pattern,
                        intensity_method=slot.intensity_method,
                        sets=slot.sets,
                        rep_min=slot.rep_min,
                        rep_max=slot.rep_max,
                        target_rir=slot.target_rir,
                        rest_seconds=slot.rest_seconds,
                        exercise=(
                            AdminTrainingTemplateExercise(
                                id=slot.exercise.id,
                                slug=slot.exercise.slug,
                                name_en=slot.exercise.name_en,
                                name_fa=slot.exercise.name_fa,
                            )
                            if slot.exercise is not None
                            else None
                        ),
                    )
                    for slot in day.slots
                ],
            )
            for day in template.days
        ],
    )


@router.get("/ai-models", response_model=AdminAiModelsResponse)
def read_ai_models(db: DatabaseSession) -> AdminAiModelsResponse:
    routing, models = list_ai_models(db)
    return AdminAiModelsResponse(
        routing=_ai_routing_detail(routing),
        models=[_ai_model_detail(model) for model in models],
    )


@router.get(
    "/training-program-templates",
    response_model=AdminTrainingProgramTemplatesResponse,
)
def read_training_program_templates(
    db: DatabaseSession,
    days_per_week: Annotated[int | None, Query(ge=2, le=6)] = None,
) -> AdminTrainingProgramTemplatesResponse:
    templates = list_training_program_templates(db, days_per_week=days_per_week)
    return AdminTrainingProgramTemplatesResponse(
        items=[_training_template_detail(template) for template in templates]
    )


@router.get(
    "/ai-generation-failures",
    response_model=list[AdminAiGenerationFailure],
)
def read_ai_generation_failures(
    db: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AdminAiGenerationFailure]:
    failures = list_generation_failures(db, limit=limit)
    return [_ai_generation_failure_detail(generation) for generation in failures]


@router.get("/ai-model-test-runs", response_model=list[AdminAiModelTestRun])
def read_ai_model_test_runs(
    db: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AdminAiModelTestRun]:
    return [_ai_model_test_run_detail(run) for run in list_ai_model_test_runs(db, limit=limit)]


@router.post(
    "/ai-models",
    response_model=AdminAiModelDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def create_ai_model_route(
    payload: AdminAiModelCreate,
    db: DatabaseSession,
) -> AdminAiModelDetail:
    return _ai_model_detail(create_ai_model(db, payload))


@router.patch(
    "/ai-models/{model_id}",
    response_model=AdminAiModelDetail,
    dependencies=[Depends(require_trusted_origin)],
)
def update_ai_model_route(
    model_id: UUID,
    payload: AdminAiModelUpdate,
    db: DatabaseSession,
) -> AdminAiModelDetail:
    return _ai_model_detail(update_ai_model(db, get_ai_model(db, model_id), payload))


@router.patch(
    "/ai-routing",
    response_model=AdminAiRoutingDetail,
    dependencies=[Depends(require_trusted_origin)],
)
def update_ai_routing_route(
    payload: AdminAiRoutingUpdate,
    db: DatabaseSession,
) -> AdminAiRoutingDetail:
    return _ai_routing_detail(update_ai_routing(db, payload))


@router.post(
    "/ai-models/sync",
    response_model=AdminAiModelSyncResponse,
    dependencies=[Depends(require_trusted_origin)],
)
async def sync_ai_models_route(
    request: Request,
    db: DatabaseSession,
    settings: AppSettings,
) -> AdminAiModelSyncResponse:
    client = request.app.state.zen_http_client
    if not isinstance(client, httpx.AsyncClient):
        raise RuntimeError("Zen HTTP client is unavailable")
    result = await sync_zen_models(db, client, settings)
    return AdminAiModelSyncResponse(
        synchronized_model_ids=result.synchronized_model_ids,
        needs_classification=result.needs_classification,
    )


@router.post(
    "/ai-models/{model_id}/test",
    response_model=AdminAiModelCheckResponse,
    dependencies=[Depends(require_trusted_origin)],
)
async def check_ai_model_route(
    model_id: UUID,
    request: Request,
    db: DatabaseSession,
    settings: AppSettings,
) -> AdminAiModelCheckResponse:
    client = request.app.state.zen_http_client
    if not isinstance(client, httpx.AsyncClient):
        raise RuntimeError("Zen HTTP client is unavailable")
    success, model, test_run = await check_ai_model(
        db,
        get_ai_model(db, model_id),
        client,
        settings,
    )
    return AdminAiModelCheckResponse(
        success=success,
        model=_ai_model_detail(model),
        test_run=_ai_model_test_run_detail(test_run),
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
        labels=sorted((item.label for item in exercise.labels), key=lambda value: value.value),
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

    if payload.body_region is None or payload.primary_muscle is None:
        if payload.body_region is not None or payload.primary_muscle is not None:
            raise _validation_error(
                "anatomy",
                "Body region and primary muscle must be provided together",
            )
        if not payload.needs_review:
            raise _validation_error("anatomy", "Unknown anatomy requires review")
        return payload
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


def _gallery_uploads(
    settings: AppSettings,
    payload: AdminExerciseCreate,
    uploads: list[UploadFile],
) -> dict[MediaAssetKey, StoredMedia]:
    stored: dict[MediaAssetKey, StoredMedia] = {}
    try:
        for asset in payload.media_assets:
            if asset.upload_index is None:
                continue
            if asset.upload_index >= len(uploads):
                raise MediaValidationError("Media upload index does not exist")
            key: MediaAssetKey = (asset.presentation, asset.role, asset.sort_order)
            if key in stored:
                raise MediaValidationError("Duplicate media gallery item")
            media = store_upload(uploads[asset.upload_index], settings)
            expected_type = MediaType.VIDEO if asset.role is MediaRole.VIDEO else MediaType.IMAGE
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
    media_files: Annotated[list[UploadFile] | None, File()] = None,
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
                (MediaPresentation.MALE, MediaRole.VIDEO, 0): media_male_video,
                (MediaPresentation.FEMALE, MediaRole.VIDEO, 0): media_female_video,
                (MediaPresentation.MALE, MediaRole.THUMBNAIL, 0): media_male_thumbnail,
                (MediaPresentation.FEMALE, MediaRole.THUMBNAIL, 0): media_female_thumbnail,
            },
        )
        stored_media_assets.update(_gallery_uploads(settings, exercise_payload, media_files or []))
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
    media_files: Annotated[list[UploadFile] | None, File()] = None,
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
                (MediaPresentation.MALE, MediaRole.VIDEO, 0): media_male_video,
                (MediaPresentation.FEMALE, MediaRole.VIDEO, 0): media_female_video,
                (MediaPresentation.MALE, MediaRole.THUMBNAIL, 0): media_male_thumbnail,
                (MediaPresentation.FEMALE, MediaRole.THUMBNAIL, 0): media_female_thumbnail,
            },
        )
        stored_media_assets.update(_gallery_uploads(settings, exercise_payload, media_files or []))
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
