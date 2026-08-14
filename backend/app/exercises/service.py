from dataclasses import dataclass
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql.elements import ColumnElement

from app.exercises.enums import Equipment, ExerciseCautionTag, MuscleGroup
from app.exercises.models import (
    Exercise,
    ExerciseAlternative,
    ExerciseCautionTagItem,
    ExerciseEquipment,
    ExerciseLabelItem,
    ExerciseSecondaryMuscle,
)
from app.exercises.schemas import ExerciseFilters
from app.exercises.seed_data import ALTERNATIVE_SEEDS, EXERCISE_SEEDS, ExerciseSeed

SEED_ID_NAMESPACE = "https://fitsho.local/exercises/"


@dataclass(frozen=True)
class SeedResult:
    exercises: int
    alternatives: int


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_exercises(
    db: Session,
    filters: ExerciseFilters,
) -> tuple[list[Exercise], int]:
    conditions: list[ColumnElement[bool]] = [Exercise.is_active.is_(True)]
    if filters.body_region is not None:
        conditions.append(Exercise.body_region == filters.body_region)
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
                selectinload(Exercise.media_assets),
                selectinload(Exercise.labels),
            )
            .order_by(Exercise.name_en.asc(), Exercise.id.asc())
            .offset((filters.page - 1) * filters.page_size)
            .limit(filters.page_size)
        )
    )
    return exercises, total


def get_active_exercise_by_slug(db: Session, slug: str) -> Exercise | None:
    return db.scalar(
        select(Exercise)
        .where(Exercise.slug == slug, Exercise.is_active.is_(True))
        .options(
            selectinload(Exercise.secondary_muscles),
            selectinload(Exercise.equipment_items),
            selectinload(Exercise.media_assets),
            selectinload(Exercise.labels),
        )
    )


def _stable_exercise_id(slug: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"{SEED_ID_NAMESPACE}{slug}")


def _apply_seed_fields(exercise: Exercise, seed: ExerciseSeed) -> None:
    exercise.name_en = seed.name_en
    exercise.name_fa = seed.name_fa
    exercise.body_region = seed.body_region
    exercise.primary_muscle = seed.primary_muscle
    exercise.muscle_focus = seed.muscle_focus
    exercise.difficulty = seed.difficulty
    exercise.movement_pattern = seed.movement_pattern
    exercise.exercise_type = seed.exercise_type
    exercise.is_programmable = seed.is_programmable
    exercise.needs_review = False
    exercise.instructions_en = list(seed.instructions_en)
    exercise.instructions_fa = list(seed.instructions_fa)
    exercise.safety_notes_en = list(seed.safety_notes_en)
    exercise.safety_notes_fa = list(seed.safety_notes_fa)
    exercise.media_path = seed.media_path
    exercise.media_type = seed.media_type
    exercise.media_source_url = seed.media_source_url
    exercise.media_license = seed.media_license
    exercise.media_attribution = seed.media_attribution
    exercise.is_active = True


def _sync_secondary_muscles(
    exercise: Exercise,
    desired: tuple[MuscleGroup, ...],
) -> None:
    desired_set = set(desired)
    for item in list(exercise.secondary_muscles):
        if item.muscle not in desired_set:
            exercise.secondary_muscles.remove(item)
    existing = {item.muscle for item in exercise.secondary_muscles}
    exercise.secondary_muscles.extend(
        ExerciseSecondaryMuscle(muscle=muscle) for muscle in desired if muscle not in existing
    )


def _sync_equipment(
    exercise: Exercise,
    desired: tuple[Equipment, ...],
) -> None:
    desired_set = set(desired)
    for item in list(exercise.equipment_items):
        if item.equipment not in desired_set:
            exercise.equipment_items.remove(item)
    existing = {item.equipment for item in exercise.equipment_items}
    exercise.equipment_items.extend(
        ExerciseEquipment(equipment=equipment) for equipment in desired if equipment not in existing
    )


def _sync_caution_tags(
    exercise: Exercise,
    desired: tuple[ExerciseCautionTag, ...],
) -> None:
    desired_set = set(desired)
    for item in list(exercise.caution_tag_items):
        if item.caution_tag not in desired_set:
            exercise.caution_tag_items.remove(item)
    existing = {item.caution_tag for item in exercise.caution_tag_items}
    exercise.caution_tag_items.extend(
        ExerciseCautionTagItem(caution_tag=caution_tag)
        for caution_tag in desired
        if caution_tag not in existing
    )


def seed_exercises(db: Session) -> SeedResult:
    slugs = [seed.slug for seed in EXERCISE_SEEDS]

    existing = {
        exercise.slug: exercise
        for exercise in db.scalars(
            select(Exercise)
            .where(Exercise.slug.in_(slugs))
            .options(
                selectinload(Exercise.caution_tag_items),
                selectinload(Exercise.secondary_muscles),
                selectinload(Exercise.equipment_items),
            )
        )
    }

    try:
        exercises_by_slug: dict[str, Exercise] = {}
        for exercise_seed in EXERCISE_SEEDS:
            exercise = existing.get(exercise_seed.slug)
            if exercise is None:
                exercise = Exercise(
                    id=_stable_exercise_id(exercise_seed.slug),
                    slug=exercise_seed.slug,
                )
                db.add(exercise)
            _apply_seed_fields(exercise, exercise_seed)
            _sync_secondary_muscles(exercise, exercise_seed.secondary_muscles)
            _sync_equipment(exercise, exercise_seed.equipment)
            exercises_by_slug[exercise_seed.slug] = exercise

            _sync_caution_tags(exercise, exercise_seed.caution_tags)
        db.flush()

        alternative_keys = {
            (
                exercises_by_slug[alternative_seed.exercise_slug].id,
                exercises_by_slug[alternative_seed.alternative_slug].id,
            )
            for alternative_seed in ALTERNATIVE_SEEDS
        }
        existing_alternatives = {
            (item.exercise_id, item.alternative_exercise_id): item
            for item in db.scalars(
                select(ExerciseAlternative).where(
                    ExerciseAlternative.exercise_id.in_(
                        {exercise_id for exercise_id, _ in alternative_keys}
                    )
                )
            )
        }
        for alternative_seed in ALTERNATIVE_SEEDS:
            exercise_id = exercises_by_slug[alternative_seed.exercise_slug].id
            alternative_id = exercises_by_slug[alternative_seed.alternative_slug].id
            item = existing_alternatives.get((exercise_id, alternative_id))
            if item is None:
                item = ExerciseAlternative(
                    exercise_id=exercise_id,
                    alternative_exercise_id=alternative_id,
                    reason_en=alternative_seed.reason_en,
                    reason_fa=alternative_seed.reason_fa,
                )
                db.add(item)
            else:
                item.reason_en = alternative_seed.reason_en
                item.reason_fa = alternative_seed.reason_fa

        db.commit()
    except Exception:
        db.rollback()
        raise

    return SeedResult(
        exercises=len(EXERCISE_SEEDS),
        alternatives=len(ALTERNATIVE_SEEDS),
    )
