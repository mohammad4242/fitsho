from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.admin.exceptions import AdminUserNotFoundError, DuplicateExerciseSlugError
from app.admin.media import StoredMedia
from app.admin.schemas import AdminExerciseCreate, AdminExerciseFilters
from app.auth.models import User
from app.auth.service import normalize_email
from app.exercises.enums import MediaType
from app.exercises.media_metadata import OWNER_ATTRIBUTION, OWNER_LICENSE
from app.exercises.models import Exercise, ExerciseEquipment, ExerciseSecondaryMuscle

PLACEHOLDER_MEDIA_PATH = "/exercises/exercise-placeholder.svg"


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
    if filters.is_active is not None:
        conditions.append(Exercise.is_active.is_(filters.is_active))
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
) -> Exercise:
    exercise = Exercise(
        slug=payload.slug,
        name_en=payload.name_en,
        name_fa=payload.name_fa,
        body_region=payload.body_region,
        primary_muscle=payload.primary_muscle,
        difficulty=payload.difficulty,
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
    )
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
