from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, object_session, selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.admin.exceptions import AdminUserNotFoundError, DuplicateExerciseSlugError
from app.admin.media import StoredMedia
from app.admin.schemas import (
    AdminExerciseCreate,
    AdminExerciseFilters,
    AdminExerciseMediaAssetInput,
)
from app.auth.models import User
from app.auth.service import normalize_email
from app.exercises.catalog_visibility import (
    normal_catalog_exclusion_conditions,
    should_exclude_special_categories,
)
from app.exercises.enums import (
    ExerciseLabel,
    MediaPresentation,
    MediaRole,
    MediaType,
)
from app.exercises.media_metadata import OWNER_ATTRIBUTION, OWNER_LICENSE
from app.exercises.models import (
    Exercise,
    ExerciseCautionTagItem,
    ExerciseEquipment,
    ExerciseLabelItem,
    ExerciseMediaAsset,
    ExerciseSecondaryMuscle,
)
from app.workouts.models import WorkoutPlanExercise

PLACEHOLDER_MEDIA_PATH = "/exercises/exercise-placeholder.svg"
MediaAssetKey = tuple[MediaPresentation, MediaRole, int]


def _media_asset_key(asset: AdminExerciseMediaAssetInput) -> MediaAssetKey:
    return asset.presentation, asset.role, asset.sort_order


def _validate_media_assets(
    existing: list[ExerciseMediaAsset],
    payload_assets: list[AdminExerciseMediaAssetInput],
    stored_assets: dict[MediaAssetKey, StoredMedia],
) -> list[tuple[AdminExerciseMediaAssetInput, ExerciseMediaAsset | None]]:
    payload_keys = [_media_asset_key(asset) for asset in payload_assets]
    if len(payload_keys) != len(set(payload_keys)):
        raise ValueError("Each presentation, media role, and display order must be unique")
    if not set(stored_assets).issubset(payload_keys):
        raise ValueError("Each uploaded media file requires matching metadata")
    existing_by_id = {asset.id: asset for asset in existing}
    existing_by_key = {
        (asset.presentation, asset.role, asset.sort_order): asset for asset in existing
    }
    resolved: list[tuple[AdminExerciseMediaAssetInput, ExerciseMediaAsset | None]] = []
    for payload_asset, key in zip(payload_assets, payload_keys, strict=True):
        asset: ExerciseMediaAsset | None = (
            existing_by_id.get(payload_asset.id) if payload_asset.id is not None else None
        )
        if payload_asset.id is not None and asset is None:
            raise ValueError("Media asset does not belong to this exercise")
        if asset is None:
            asset = existing_by_key.get(key)
        if asset is not None and (
            asset.presentation is not payload_asset.presentation
            or asset.role is not payload_asset.role
        ):
            raise ValueError("Media asset presentation cannot be changed")
        if asset is None and key not in stored_assets:
            raise ValueError("New media metadata requires its media file")
        resolved.append((payload_asset, asset))
    return resolved


def _sync_media_assets(
    exercise: Exercise,
    payload_assets: list[AdminExerciseMediaAssetInput],
    stored_assets: dict[MediaAssetKey, StoredMedia],
) -> None:
    resolved = _validate_media_assets(list(exercise.media_assets), payload_assets, stored_assets)
    if exercise.media_assets:
        temporary_base = max(
            [asset.sort_order for asset in exercise.media_assets]
            + [asset.sort_order for asset in payload_assets]
            + [0]
        ) + len(exercise.media_assets) + 1
        for index, existing_asset in enumerate(exercise.media_assets):
            existing_asset.sort_order = temporary_base + index
        exercise_db = object_session(exercise)
        if exercise_db is not None:
            exercise_db.flush()

    for payload_asset, asset in resolved:
        key = _media_asset_key(payload_asset)
        stored_media = stored_assets.get(key)
        if asset is None:
            assert stored_media is not None
            asset = ExerciseMediaAsset(
                presentation=payload_asset.presentation,
                role=payload_asset.role,
                sort_order=payload_asset.sort_order,
                media_path=stored_media.public_path,
                media_type=stored_media.media_type,
            )
            exercise.media_assets.append(asset)
        else:
            asset.sort_order = payload_asset.sort_order
        if stored_media is not None:
            asset.media_path = stored_media.public_path
            asset.media_type = stored_media.media_type
        asset.media_source_url = payload_asset.media_source_url
        asset.media_license = payload_asset.media_license or (
            OWNER_LICENSE if stored_media is not None else asset.media_license
        )
        asset.media_attribution = payload_asset.media_attribution or (
            OWNER_ATTRIBUTION if stored_media is not None else asset.media_attribution
        )
    desired_keys = {_media_asset_key(asset) for asset in payload_assets}
    for asset in list(exercise.media_assets):
        if (
            asset.presentation,
            asset.role,
            asset.sort_order,
        ) not in desired_keys:
            exercise.media_assets.remove(asset)


def _sync_labels(exercise: Exercise, desired: list[ExerciseLabel]) -> None:
    desired_set = set(desired)
    for item in list(exercise.labels):
        if item.label not in desired_set:
            exercise.labels.remove(item)
    existing = {item.label for item in exercise.labels}
    exercise.labels.extend(
        ExerciseLabelItem(label=label)
        for label in sorted(desired_set, key=lambda value: value.value)
        if label not in existing
    )


def grant_admin(db: Session, email: str) -> User:
    user = db.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        raise AdminUserNotFoundError
    if user.is_admin:
        return user

    user.is_admin = True
    try:
        db.commit()
        db.refresh(user)
    except SQLAlchemyError:
        db.rollback()
        raise
    return user


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_admin_exercises(
    db: Session,
    filters: AdminExerciseFilters,
) -> tuple[list[Exercise], int]:
    conditions: list[ColumnElement[bool]] = []
    if filters.body_region is not None:
        conditions.append(Exercise.body_region == filters.body_region)
    if filters.content_type is not None:
        conditions.append(Exercise.content_type == filters.content_type)
    if filters.primary_muscle is not None:
        conditions.append(Exercise.primary_muscle == filters.primary_muscle)
    if filters.muscle_focus is not None:
        conditions.append(Exercise.muscle_focus == filters.muscle_focus)
    if filters.equipment is not None:
        conditions.append(
            Exercise.equipment_items.any(ExerciseEquipment.equipment == filters.equipment)
        )
    if filters.difficulty is not None:
        conditions.append(Exercise.difficulty == filters.difficulty)
    if filters.exercise_type is not None:
        conditions.append(Exercise.exercise_type == filters.exercise_type)
    if filters.labels:
        conditions.extend(
            Exercise.labels.any(ExerciseLabelItem.label == label) for label in filters.labels
        )
    if should_exclude_special_categories(filters.labels, filters.exercise_type):
        conditions.extend(normal_catalog_exclusion_conditions())
    if filters.is_active is not None:
        conditions.append(Exercise.is_active.is_(filters.is_active))
    if filters.needs_review is not None:
        conditions.append(Exercise.needs_review.is_(filters.needs_review))
    if filters.search is not None:
        pattern = f"%{_escape_like(filters.search)}%"
        conditions.append(
            or_(
                Exercise.name_en.ilike(pattern, escape="\\"),
                Exercise.name_fa.ilike(pattern, escape="\\"),
                Exercise.slug.ilike(pattern, escape="\\"),
            )
        )

    total = db.scalar(select(func.count()).select_from(Exercise).where(*conditions)) or 0
    exercises = list(
        db.scalars(
            select(Exercise)
            .where(*conditions)
            .options(
                selectinload(Exercise.secondary_muscles),
                selectinload(Exercise.equipment_items),
                selectinload(Exercise.caution_tag_items),
                selectinload(Exercise.media_assets),
                selectinload(Exercise.labels),
            )
            .order_by(Exercise.created_at.desc(), Exercise.id.asc())
            .offset((filters.page - 1) * filters.page_size)
            .limit(filters.page_size)
        )
    )
    return exercises, total


def create_admin_exercise(
    db: Session,
    payload: AdminExerciseCreate,
    media: StoredMedia | None = None,
    media_assets: dict[MediaAssetKey, StoredMedia] | None = None,
) -> Exercise:
    stored_media_assets = media_assets or {}
    _validate_media_assets([], payload.media_assets, stored_media_assets)
    exercise = Exercise(
        slug=payload.slug,
        name_en=payload.name_en,
        name_fa=payload.name_fa,
        content_type=payload.content_type,
        body_region=payload.body_region,
        primary_muscle=payload.primary_muscle,
        muscle_focus=payload.muscle_focus,
        difficulty=payload.difficulty,
        movement_pattern=payload.movement_pattern,
        exercise_type=payload.exercise_type,
        is_programmable=payload.is_programmable,
        body_position=payload.body_position,
        stability_demand=payload.stability_demand,
        skill_demand=payload.skill_demand,
        impact_level=payload.impact_level,
        axial_loading_level=payload.axial_loading_level,
        fatigue_cost=payload.fatigue_cost,
        setup_cost=payload.setup_cost,
        laterality=payload.laterality,
        substitution_group=payload.substitution_group,
        range_of_motion_profile=payload.range_of_motion_profile,
        instructions_en=payload.instructions_en,
        instructions_fa=payload.instructions_fa,
        safety_notes_en=payload.safety_notes_en,
        safety_notes_fa=payload.safety_notes_fa,
        media_path=media.public_path if media is not None else PLACEHOLDER_MEDIA_PATH,
        media_type=media.media_type if media is not None else MediaType.PLACEHOLDER,
        media_source_url=payload.media_source_url,
        media_license=payload.media_license or (OWNER_LICENSE if media is not None else None),
        media_attribution=payload.media_attribution
        or (OWNER_ATTRIBUTION if media is not None else None),
        is_active=payload.is_active,
        secondary_muscles=[
            ExerciseSecondaryMuscle(muscle=muscle)
            for muscle in sorted(set(payload.secondary_muscles), key=lambda value: value.value)
        ],
        equipment_items=[
            ExerciseEquipment(equipment=equipment)
            for equipment in sorted(set(payload.equipment), key=lambda value: value.value)
        ],
        caution_tag_items=[
            ExerciseCautionTagItem(caution_tag=tag)
            for tag in sorted(set(payload.caution_tags), key=lambda value: value.value)
        ],
        labels=[
            ExerciseLabelItem(label=label)
            for label in sorted(set(payload.labels), key=lambda value: value.value)
        ],
        needs_review=payload.needs_review,
    )
    _sync_media_assets(exercise, payload.media_assets, stored_media_assets)
    db.add(exercise)
    try:
        db.commit()
        db.refresh(exercise)
    except IntegrityError as error:
        db.rollback()
        raise DuplicateExerciseSlugError from error
    except SQLAlchemyError:
        db.rollback()
        raise
    return exercise


def get_admin_exercise(db: Session, exercise_id: UUID) -> Exercise | None:
    return db.scalar(
        select(Exercise)
        .where(Exercise.id == exercise_id)
        .options(
            selectinload(Exercise.secondary_muscles),
            selectinload(Exercise.equipment_items),
            selectinload(Exercise.caution_tag_items),
            selectinload(Exercise.media_assets),
            selectinload(Exercise.labels),
        )
    )


def update_admin_exercise(
    db: Session,
    exercise_id: UUID,
    payload: AdminExerciseCreate,
    media: StoredMedia | None = None,
    media_assets: dict[MediaAssetKey, StoredMedia] | None = None,
) -> Exercise | None:
    exercise = db.scalar(
        select(Exercise)
        .where(Exercise.id == exercise_id)
        .options(
            selectinload(Exercise.secondary_muscles),
            selectinload(Exercise.equipment_items),
            selectinload(Exercise.caution_tag_items),
            selectinload(Exercise.media_assets),
            selectinload(Exercise.labels),
        )
        .with_for_update()
    )
    if exercise is None:
        return None

    for field in (
        "slug",
        "name_en",
        "name_fa",
        "content_type",
        "body_region",
        "primary_muscle",
        "muscle_focus",
        "difficulty",
        "movement_pattern",
        "exercise_type",
        "is_programmable",
        "body_position",
        "stability_demand",
        "skill_demand",
        "impact_level",
        "axial_loading_level",
        "fatigue_cost",
        "setup_cost",
        "laterality",
        "substitution_group",
        "range_of_motion_profile",
        "instructions_en",
        "instructions_fa",
        "safety_notes_en",
        "safety_notes_fa",
        "media_source_url",
        "media_license",
        "media_attribution",
        "is_active",
        "needs_review",
    ):
        setattr(exercise, field, getattr(payload, field))
    exercise.secondary_muscles[:] = [
        ExerciseSecondaryMuscle(muscle=muscle)
        for muscle in sorted(set(payload.secondary_muscles), key=lambda value: value.value)
    ]
    exercise.equipment_items[:] = [
        ExerciseEquipment(equipment=equipment)
        for equipment in sorted(set(payload.equipment), key=lambda value: value.value)
    ]
    exercise.caution_tag_items[:] = [
        ExerciseCautionTagItem(caution_tag=tag)
        for tag in sorted(set(payload.caution_tags), key=lambda value: value.value)
    ]
    _sync_labels(exercise, payload.labels)
    if media is not None:
        exercise.media_path = media.public_path
        exercise.media_type = media.media_type
    _sync_media_assets(exercise, payload.media_assets, media_assets or {})

    try:
        db.commit()
        db.refresh(exercise)
    except IntegrityError as error:
        db.rollback()
        raise DuplicateExerciseSlugError from error
    except SQLAlchemyError:
        db.rollback()
        raise
    return exercise


def delete_admin_exercise(db: Session, exercise_id: UUID) -> list[str] | None:
    exercise = db.scalar(
        select(Exercise)
        .where(Exercise.id == exercise_id)
        .options(selectinload(Exercise.media_assets))
        .with_for_update()
    )
    if exercise is None:
        return None

    media_paths = [exercise.media_path, *(asset.media_path for asset in exercise.media_assets)]
    db.execute(
        delete(WorkoutPlanExercise).where(WorkoutPlanExercise.exercise_id == exercise_id)
    )
    db.delete(exercise)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise
    return media_paths
