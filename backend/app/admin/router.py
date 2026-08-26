from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from pydantic import ValidationError

from app.admin.dependencies import require_admin
from app.admin.exceptions import DuplicateExerciseSlugError
from app.admin.media import (
    MediaValidationError,
    StoredMedia,
    discard_managed_media_file,
    discard_media,
    store_upload,
)
from app.admin.schemas import (
    AdminExerciseCreate,
    AdminExerciseDetail,
    AdminExerciseFilters,
    AdminExerciseMediaAssetDetail,
    AdminTrainingProgramStructure,
    AdminTrainingProgramStructuresResponse,
    AdminTrainingProgramStructureWrite,
    AdminTrainingProgramTemplate,
    AdminTrainingProgramTemplatesResponse,
    AdminTrainingProgramTemplateWrite,
    AdminTrainingTemplateDay,
    AdminTrainingTemplateExercise,
    AdminTrainingTemplateSlot,
    AdminTrainingTemplateSlotWrite,
    PaginatedAdminExercises,
)
from app.admin.service import (
    MediaAssetKey,
    create_admin_exercise,
    delete_admin_exercise,
    get_admin_exercise,
    list_admin_exercises,
    update_admin_exercise,
)
from app.auth.cookies import require_trusted_origin
from app.auth.dependencies import AppSettings, DatabaseSession
from app.exercises.enums import MediaPresentation, MediaRole, MediaType
from app.exercises.models import Exercise
from app.exercises.taxonomy import MUSCLES_BY_REGION, is_compatible_muscle_focus
from app.profile.enums import ExperienceLevel
from app.training_templates.admin_service import (
    StructureWriteError,
    TemplateWriteError,
    create_training_program_structure,
    create_training_program_template,
    delete_training_program_structure,
    delete_training_program_template,
    delete_training_program_template_slot,
    get_training_program_structure,
    get_training_program_template,
    list_training_program_structures,
    set_structure_active,
    update_training_program_structure,
    update_training_program_template,
    update_training_program_template_slot,
)
from app.training_templates.models import (
    StructureFamily,
    TrainingProgramStructure,
    TrainingProgramTemplate,
)
from app.training_templates.service import list_training_program_templates

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
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
        supported_levels=template.supported_levels,
        focus_tags=template.focus_tags,
        intensity_methods=template.intensity_methods,
        programming_rationale=template.programming_rationale,
        source_name=template.source_name,
        source_url=template.source_url,
        structure_id=template.structure_id,
        days=[
            AdminTrainingTemplateDay(
                id=day.id,
                day_number=day.day_number,
                title_en=day.title_en,
                title_fa=day.title_fa,
                structure_focus=day.structure_focus,
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
                        adaptation_priority=slot.adaptation_priority,
                        superset_group=slot.superset_group,
                        superset_exercise_id=slot.superset_exercise_id,
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
                                needs_review=slot.exercise.needs_review,
                            )
                            if slot.exercise is not None
                            else None
                        ),
                        superset_exercise=(
                            AdminTrainingTemplateExercise(
                                id=slot.superset_exercise.id,
                                slug=slot.superset_exercise.slug,
                                name_en=slot.superset_exercise.name_en,
                                name_fa=slot.superset_exercise.name_fa,
                                needs_review=slot.superset_exercise.needs_review,
                            )
                            if slot.superset_exercise is not None
                            else None
                        ),
                    )
                    for slot in day.slots
                ],
            )
            for day in template.days
        ],
    )


def _structure_detail(structure: TrainingProgramStructure) -> AdminTrainingProgramStructure:
    from app.admin.schemas import AdminTrainingProgramStructureDay as DaySchema

    return AdminTrainingProgramStructure(
        id=structure.id,
        slug=structure.slug,
        name_en=structure.name_en,
        name_fa=structure.name_fa,
        days_per_week=structure.days_per_week,
        family=structure.family,
        split_type=structure.split_type,
        description_en=structure.description_en,
        description_fa=structure.description_fa,
        is_active=structure.is_active,
        structure_days=[
            DaySchema(
                id=day.id,
                day_number=day.day_number,
                label_en=day.label_en,
                label_fa=day.label_fa,
                day_type=day.day_type,
            )
            for day in structure.structure_days
        ],
    )


# ---------------------------------------------------------------------------
# Training Program Structure endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/training-program-structures",
    response_model=AdminTrainingProgramStructuresResponse,
)
def read_training_program_structures(
    db: DatabaseSession,
    days_per_week: Annotated[int | None, Query(ge=2, le=6)] = None,
    family: StructureFamily | None = None,
    include_inactive: bool = False,
) -> AdminTrainingProgramStructuresResponse:
    structures = list_training_program_structures(
        db,
        days_per_week=days_per_week,
        family=family,
        include_inactive=include_inactive,
    )
    return AdminTrainingProgramStructuresResponse(items=[_structure_detail(s) for s in structures])


@router.get(
    "/training-program-structures/{structure_id}",
    response_model=AdminTrainingProgramStructure,
)
def read_training_program_structure(
    structure_id: UUID,
    db: DatabaseSession,
) -> AdminTrainingProgramStructure:
    structure = get_training_program_structure(db, structure_id)
    if structure is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Structure not found")
    return _structure_detail(structure)


@router.post(
    "/training-program-structures",
    response_model=AdminTrainingProgramStructure,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def create_structure(
    payload: AdminTrainingProgramStructureWrite,
    db: DatabaseSession,
) -> AdminTrainingProgramStructure:
    try:
        structure = create_training_program_structure(db, payload)
    except StructureWriteError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return _structure_detail(structure)


@router.put(
    "/training-program-structures/{structure_id}",
    response_model=AdminTrainingProgramStructure,
    dependencies=[Depends(require_trusted_origin)],
)
def update_structure(
    structure_id: UUID,
    payload: AdminTrainingProgramStructureWrite,
    db: DatabaseSession,
) -> AdminTrainingProgramStructure:
    try:
        structure = update_training_program_structure(db, structure_id, payload)
    except StructureWriteError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    if structure is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Structure not found")
    return _structure_detail(structure)


@router.patch(
    "/training-program-structures/{structure_id}/activate",
    response_model=AdminTrainingProgramStructure,
    dependencies=[Depends(require_trusted_origin)],
)
def activate_structure(
    structure_id: UUID,
    db: DatabaseSession,
) -> AdminTrainingProgramStructure:
    structure = set_structure_active(db, structure_id, is_active=True)
    if structure is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Structure not found")
    return _structure_detail(structure)


@router.patch(
    "/training-program-structures/{structure_id}/deactivate",
    response_model=AdminTrainingProgramStructure,
    dependencies=[Depends(require_trusted_origin)],
)
def deactivate_structure(
    structure_id: UUID,
    db: DatabaseSession,
) -> AdminTrainingProgramStructure:
    structure = set_structure_active(db, structure_id, is_active=False)
    if structure is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Structure not found")
    return _structure_detail(structure)


@router.delete(
    "/training-program-structures/{structure_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_trusted_origin)],
)
def delete_structure(
    structure_id: UUID,
    db: DatabaseSession,
) -> Response:
    try:
        found = delete_training_program_structure(db, structure_id)
    except StructureWriteError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Structure not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/training-program-templates",
    response_model=AdminTrainingProgramTemplatesResponse,
)
def read_training_program_templates(
    db: DatabaseSession,
    days_per_week: Annotated[int | None, Query(ge=2, le=6)] = None,
    training_level: ExperienceLevel | None = None,
    family: StructureFamily | None = None,
    structure_id: UUID | None = None,
) -> AdminTrainingProgramTemplatesResponse:
    templates = list_training_program_templates(
        db,
        days_per_week=days_per_week,
        training_level=training_level,
        family=family,
        structure_id=structure_id,
    )
    return AdminTrainingProgramTemplatesResponse(
        items=[_training_template_detail(template) for template in templates]
    )


@router.get(
    "/training-program-templates/{template_id}",
    response_model=AdminTrainingProgramTemplate,
)
def read_training_program_template(
    template_id: UUID,
    db: DatabaseSession,
) -> AdminTrainingProgramTemplate:
    template = get_training_program_template(db, template_id)
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program template not found",
        )
    return _training_template_detail(template)


@router.post(
    "/training-program-templates",
    response_model=AdminTrainingProgramTemplate,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_trusted_origin)],
)
def create_training_template(
    payload: AdminTrainingProgramTemplateWrite,
    db: DatabaseSession,
) -> AdminTrainingProgramTemplate:
    try:
        return _training_template_detail(create_training_program_template(db, payload))
    except TemplateWriteError as error:
        raise _validation_error("days", str(error)) from None


@router.put(
    "/training-program-templates/{template_id}",
    response_model=AdminTrainingProgramTemplate,
    dependencies=[Depends(require_trusted_origin)],
)
def update_training_template(
    template_id: UUID,
    payload: AdminTrainingProgramTemplateWrite,
    db: DatabaseSession,
) -> AdminTrainingProgramTemplate:
    try:
        template = update_training_program_template(db, template_id, payload)
    except TemplateWriteError as error:
        raise _validation_error("days", str(error)) from None
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program template not found",
        )
    return _training_template_detail(template)


@router.patch(
    "/training-program-templates/{template_id}/days/{day_id}/slots/{slot_id}",
    response_model=AdminTrainingProgramTemplate,
    dependencies=[Depends(require_trusted_origin)],
)
def update_training_template_slot(
    template_id: UUID,
    day_id: UUID,
    slot_id: UUID,
    payload: AdminTrainingTemplateSlotWrite,
    db: DatabaseSession,
) -> AdminTrainingProgramTemplate:
    try:
        template = update_training_program_template_slot(db, template_id, day_id, slot_id, payload)
    except TemplateWriteError as error:
        raise _validation_error("slot", str(error)) from None
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Training template slot not found",
        )
    return _training_template_detail(template)


@router.delete(
    "/training-program-templates/{template_id}/days/{day_id}/slots/{slot_id}",
    response_model=AdminTrainingProgramTemplate,
    dependencies=[Depends(require_trusted_origin)],
)
def delete_training_template_slot(
    template_id: UUID,
    day_id: UUID,
    slot_id: UUID,
    db: DatabaseSession,
) -> AdminTrainingProgramTemplate:
    try:
        template = delete_training_program_template_slot(db, template_id, day_id, slot_id)
    except TemplateWriteError as error:
        raise _validation_error("slot", str(error)) from None
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Training template slot not found",
        )
    return _training_template_detail(template)


@router.delete(
    "/training-program-templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_trusted_origin)],
)
def delete_training_template(template_id: UUID, db: DatabaseSession) -> Response:
    if not delete_training_program_template(db, template_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program template not found",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _detail(exercise: Exercise) -> AdminExerciseDetail:
    return AdminExerciseDetail(
        id=exercise.id,
        slug=exercise.slug,
        name_en=exercise.name_en,
        name_fa=exercise.name_fa,
        content_type=exercise.content_type,
        body_region=exercise.body_region,
        primary_muscle=exercise.primary_muscle,
        muscle_focus=exercise.muscle_focus,
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
            AdminExerciseMediaAssetDetail(
                id=asset.id,
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
        body_position=exercise.body_position,
        stability_demand=exercise.stability_demand,
        skill_demand=exercise.skill_demand,
        impact_level=exercise.impact_level,
        axial_loading_level=exercise.axial_loading_level,
        fatigue_cost=exercise.fatigue_cost,
        setup_cost=exercise.setup_cost,
        laterality=exercise.laterality,
        substitution_group=exercise.substitution_group,
        range_of_motion_profile=exercise.range_of_motion_profile,
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
        if payload.muscle_focus is not None:
            raise _validation_error("muscle_focus", "Unknown anatomy cannot have muscle focus")
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
    if not is_compatible_muscle_focus(payload.primary_muscle, payload.muscle_focus):
        raise _validation_error(
            "muscle_focus",
            "Muscle focus must belong to the selected primary muscle",
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
            expected_type = MediaType.VIDEO
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
            expected_type = MediaType.VIDEO
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


@router.delete(
    "/exercises/{exercise_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_trusted_origin)],
)
def delete_exercise(
    exercise_id: UUID,
    db: DatabaseSession,
    settings: AppSettings,
) -> None:
    media_paths = delete_admin_exercise(db, exercise_id)
    if media_paths is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    for media_path in media_paths:
        discard_managed_media_file(media_path, settings)


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
