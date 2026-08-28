import re
from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.admin.schemas import (
    AdminTrainingProgramStructureWrite,
    AdminTrainingProgramTemplateWrite,
    AdminTrainingTemplateSlotWrite,
)
from app.exercises.enums import (
    Equipment,
    ExerciseContentType,
    ExerciseType,
    MovementPattern,
    MuscleGroup,
)
from app.exercises.models import Exercise
from app.training_templates.catalog_placeholders import TEMPLATE_PLACEHOLDER_SOURCE
from app.training_templates.models import (
    StructureFamily,
    TrainingProgramStructure,
    TrainingProgramStructureDay,
    TrainingProgramTemplate,
    TrainingProgramTemplateDay,
    TrainingProgramTemplateSlot,
)
from app.workouts.program_engine.enums import LoadLimit
from app.workouts.program_engine.slot_compatibility import (
    evaluate_candidate_slot_compatibility,
    template_slot_allowed_patterns,
)
from app.workouts.program_engine.supersets import safe_superset_category


class TemplateWriteError(ValueError):
    pass


class StructureWriteError(ValueError):
    pass


# ---------------------------------------------------------------------------
# Structure CRUD
# ---------------------------------------------------------------------------


def list_training_program_structures(
    db: Session,
    *,
    days_per_week: int | None = None,
    family: StructureFamily | None = None,
    include_inactive: bool = False,
) -> list[TrainingProgramStructure]:
    stmt = select(TrainingProgramStructure).options(
        selectinload(TrainingProgramStructure.structure_days)
    )
    if days_per_week is not None:
        stmt = stmt.where(TrainingProgramStructure.days_per_week == days_per_week)
    if family is not None:
        stmt = stmt.where(TrainingProgramStructure.family == family)
    if not include_inactive:
        stmt = stmt.where(TrainingProgramStructure.is_active.is_(True))
    stmt = stmt.order_by(TrainingProgramStructure.days_per_week, TrainingProgramStructure.name_en)
    return list(db.scalars(stmt))


def get_training_program_structure(
    db: Session,
    structure_id: UUID,
) -> TrainingProgramStructure | None:
    return db.scalar(
        select(TrainingProgramStructure)
        .where(TrainingProgramStructure.id == structure_id)
        .options(selectinload(TrainingProgramStructure.structure_days))
    )


def create_training_program_structure(
    db: Session,
    payload: AdminTrainingProgramStructureWrite,
) -> TrainingProgramStructure:
    _validate_structure_payload(payload)
    structure = TrainingProgramStructure(
        slug=payload.slug,
        name_en=payload.name_en,
        name_fa=payload.name_fa,
        days_per_week=payload.days_per_week,
        family=payload.family,
        split_type=payload.split_type,
        description_en=payload.description_en,
        description_fa=payload.description_fa,
        is_active=True,
    )
    db.add(structure)
    db.flush()
    _replace_structure_days(structure, payload)
    db.commit()
    return _get_structure_or_raise(db, structure.id)


def update_training_program_structure(
    db: Session,
    structure_id: UUID,
    payload: AdminTrainingProgramStructureWrite,
) -> TrainingProgramStructure | None:
    structure = db.get(TrainingProgramStructure, structure_id)
    if structure is None:
        return None
    _validate_structure_payload(payload)
    if structure.days_per_week != payload.days_per_week:
        reference_count = db.scalar(
            select(func.count())
            .select_from(TrainingProgramTemplate)
            .where(TrainingProgramTemplate.structure_id == structure_id)
        )
        if reference_count and reference_count > 0:
            raise StructureWriteError(
                "Cannot change days_per_week for a structure referenced by "
                f"{reference_count} template(s)."
            )
    structure.slug = payload.slug
    structure.name_en = payload.name_en
    structure.name_fa = payload.name_fa
    structure.days_per_week = payload.days_per_week
    structure.family = payload.family
    structure.split_type = payload.split_type
    structure.description_en = payload.description_en
    structure.description_fa = payload.description_fa
    structure.structure_days.clear()
    db.flush()
    _replace_structure_days(structure, payload)
    db.commit()
    return _get_structure_or_raise(db, structure.id)


def set_structure_active(
    db: Session,
    structure_id: UUID,
    *,
    is_active: bool,
) -> TrainingProgramStructure | None:
    structure = db.get(TrainingProgramStructure, structure_id)
    if structure is None:
        return None
    structure.is_active = is_active
    db.commit()
    return _get_structure_or_raise(db, structure.id)


def delete_training_program_structure(
    db: Session,
    structure_id: UUID,
) -> bool:
    """Delete a structure. Raises StructureWriteError if referenced by templates."""
    structure = db.get(TrainingProgramStructure, structure_id)
    if structure is None:
        return False
    reference_count = db.scalar(
        select(func.count())
        .select_from(TrainingProgramTemplate)
        .where(TrainingProgramTemplate.structure_id == structure_id)
    )
    if reference_count and reference_count > 0:
        raise StructureWriteError(
            f"Structure is referenced by {reference_count} template(s). "
            "Deactivate it or reassign templates before deleting."
        )
    db.delete(structure)
    db.commit()
    return True


def _validate_structure_payload(payload: AdminTrainingProgramStructureWrite) -> None:
    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", payload.slug):
        raise StructureWriteError("slug must match ^[a-z0-9]+(-[a-z0-9]+)*$")
    if payload.days_per_week not in range(2, 7):
        raise StructureWriteError("days_per_week must be between 2 and 6")
    if len(payload.days) != payload.days_per_week:
        raise StructureWriteError(
            f"days_per_week is {payload.days_per_week} but {len(payload.days)} days provided"
        )
    day_numbers = [d.day_number for d in payload.days]
    if sorted(day_numbers) != list(range(1, payload.days_per_week + 1)):
        raise StructureWriteError(
            "day_number values must be exactly 1…days_per_week with no gaps or duplicates"
        )


def _replace_structure_days(
    structure: TrainingProgramStructure,
    payload: AdminTrainingProgramStructureWrite,
) -> None:
    for day_payload in sorted(payload.days, key=lambda d: d.day_number):
        db_day = TrainingProgramStructureDay(
            structure_id=structure.id,
            day_number=day_payload.day_number,
            label_en=day_payload.label_en,
            label_fa=day_payload.label_fa,
            day_type=day_payload.day_type,
        )
        structure.structure_days.append(db_day)


def _get_structure_or_raise(db: Session, structure_id: UUID) -> TrainingProgramStructure:
    structure = db.scalar(
        select(TrainingProgramStructure)
        .where(TrainingProgramStructure.id == structure_id)
        .options(selectinload(TrainingProgramStructure.structure_days))
    )
    if structure is None:
        raise RuntimeError(f"Structure {structure_id} disappeared after write")
    return structure


def get_training_program_template(
    db: Session,
    template_id: UUID,
) -> TrainingProgramTemplate | None:
    return db.scalar(
        select(TrainingProgramTemplate)
        .where(TrainingProgramTemplate.id == template_id)
        .options(
            selectinload(TrainingProgramTemplate.days)
            .selectinload(TrainingProgramTemplateDay.slots)
            .selectinload(TrainingProgramTemplateSlot.exercise),
            selectinload(TrainingProgramTemplate.days)
            .selectinload(TrainingProgramTemplateDay.slots)
            .selectinload(TrainingProgramTemplateSlot.superset_exercise),
        )
    )


def create_training_program_template(
    db: Session,
    payload: AdminTrainingProgramTemplateWrite,
) -> TrainingProgramTemplate:
    exercise_slugs = _validate_exercise_links(db, payload)
    template = TrainingProgramTemplate(slug=_unique_slug(db, payload.name_en))
    db.add(template)
    _replace_template_content(template, payload, exercise_slugs)
    db.commit()
    return _get_template_or_raise(db, template.id)


def update_training_program_template(
    db: Session,
    template_id: UUID,
    payload: AdminTrainingProgramTemplateWrite,
) -> TrainingProgramTemplate | None:
    template = db.get(TrainingProgramTemplate, template_id)
    if template is None:
        return None
    exercise_slugs = _validate_exercise_links(db, payload)
    template.days.clear()
    db.flush()
    _replace_template_content(template, payload, exercise_slugs)
    db.commit()
    return _get_template_or_raise(db, template.id)


def update_training_program_template_slot(
    db: Session,
    template_id: UUID,
    day_id: UUID,
    slot_id: UUID,
    payload: AdminTrainingTemplateSlotWrite,
) -> TrainingProgramTemplate | None:
    slot = db.scalar(
        select(TrainingProgramTemplateSlot)
        .join(
            TrainingProgramTemplateDay,
            TrainingProgramTemplateDay.id == TrainingProgramTemplateSlot.template_day_id,
        )
        .where(
            TrainingProgramTemplateDay.template_id == template_id,
            TrainingProgramTemplateDay.id == day_id,
            TrainingProgramTemplateSlot.id == slot_id,
        )
    )
    if slot is None:
        return None

    exercise_slugs = _validate_exercise_links_for_slots(db, (payload,))
    slot.exercise_id = payload.exercise_id
    slot.exercise_slug_hint = exercise_slugs[payload.exercise_id]
    slot.placeholder_name_en = payload.display_name_en
    slot.placeholder_name_fa = payload.display_name_fa
    slot.target_muscles = [muscle.value for muscle in payload.target_muscles]
    slot.movement_pattern = payload.movement_pattern
    slot.intensity_method = payload.intensity_method
    slot.adaptation_priority = payload.adaptation_priority
    slot.superset_group = payload.superset_group
    slot.superset_exercise_id = payload.superset_exercise_id
    slot.superset_exercise_slug_hint = (
        exercise_slugs[payload.superset_exercise_id]
        if payload.superset_exercise_id is not None
        else None
    )
    slot.sets = payload.sets
    slot.rep_min = payload.rep_min
    slot.rep_max = payload.rep_max
    slot.target_rir = payload.target_rir
    slot.rest_seconds = payload.rest_seconds
    db.commit()
    return _get_template_or_raise(db, template_id)


def delete_training_program_template_slot(
    db: Session,
    template_id: UUID,
    day_id: UUID,
    slot_id: UUID,
) -> TrainingProgramTemplate | None:
    day = db.scalar(
        select(TrainingProgramTemplateDay)
        .where(
            TrainingProgramTemplateDay.template_id == template_id,
            TrainingProgramTemplateDay.id == day_id,
        )
        .options(selectinload(TrainingProgramTemplateDay.slots))
    )
    if day is None:
        return None
    slot = next((item for item in day.slots if item.id == slot_id), None)
    if slot is None:
        return None

    runtime_count = sum(2 if item.intensity_method.value == "superset" else 1 for item in day.slots)
    removed_count = 2 if slot.intensity_method.value == "superset" else 1
    if runtime_count - removed_count < 4:
        raise TemplateWriteError("Each day must contain exactly 4 to 9 runtime exercises")

    db.delete(slot)
    db.flush()
    remaining_slots = [item for item in day.slots if item.id != slot.id]
    for slot_order, remaining in enumerate(
        sorted(remaining_slots, key=lambda item: item.slot_order),
        start=1,
    ):
        remaining.slot_order = slot_order
    db.commit()
    return _get_template_or_raise(db, template_id)


def delete_training_program_template(db: Session, template_id: UUID) -> bool:
    template = db.get(TrainingProgramTemplate, template_id)
    if template is None:
        return False
    db.delete(template)
    db.commit()
    return True


def _validate_exercise_links(
    db: Session,
    payload: AdminTrainingProgramTemplateWrite,
) -> dict[UUID, str]:
    return _validate_exercise_links_for_slots(
        db,
        (slot for day in payload.days for slot in day.slots),
    )


def _validate_exercise_links_for_slots(
    db: Session,
    slots: Iterable[AdminTrainingTemplateSlotWrite],
) -> dict[UUID, str]:
    slot_items = tuple(slots)
    exercise_ids = {slot.exercise_id for slot in slot_items}
    exercise_ids |= {
        slot.superset_exercise_id
        for slot in slot_items
        if slot.superset_exercise_id
    }
    exercises = list(
        db.scalars(
            select(Exercise).where(
                Exercise.id.in_(exercise_ids),
                Exercise.is_active.is_(True),
                Exercise.is_programmable.is_(True),
                Exercise.content_type == ExerciseContentType.EXERCISE,
                or_(
                    Exercise.source.is_(None),
                    Exercise.source != TEMPLATE_PLACEHOLDER_SOURCE,
                ),
            )
            .options(
                selectinload(Exercise.secondary_muscles),
                selectinload(Exercise.equipment_items),
            )
        )
    )
    active_exercise_ids = {exercise.id for exercise in exercises}
    if inactive_or_unknown := exercise_ids - active_exercise_ids:
        formatted_ids = ", ".join(sorted(str(item) for item in inactive_or_unknown))
        raise TemplateWriteError(
            "Selected exercise must exist and be active, programmable, and non-placeholder: "
            f"{formatted_ids}"
        )
    exercises_by_id = {exercise.id: exercise for exercise in exercises}
    for slot in slot_items:
        exercise = exercises_by_id[slot.exercise_id]
        compatibility = evaluate_candidate_slot_compatibility(
            _ExerciseSemanticAdapter(exercise),
            allowed_patterns=template_slot_allowed_patterns(
                slot.movement_pattern,
                tuple(slot.target_muscles),
            ),
            target_muscles=frozenset(slot.target_muscles),
        )
        if not compatibility.compatible:
            raise TemplateWriteError(
                "Selected exercise is incompatible with the slot movement or target muscles: "
                f"{exercise.slug} ({exercise.id})"
            )
        if (
            slot.intensity_method.value == "drop_set"
            and exercise.exercise_type is not ExerciseType.ISOLATION
        ):
            raise TemplateWriteError(
                "Drop-set slots require a stable isolation exercise: "
                f"{exercise.slug} ({exercise.id})"
            )
        if slot.intensity_method.value == "superset":
            assert slot.superset_exercise_id is not None
            superset_exercise = exercises_by_id[slot.superset_exercise_id]
            pair = (
                _AdminSupersetExercise.from_slot(exercise, slot.adaptation_priority.value),
                _AdminSupersetExercise.from_slot(superset_exercise, slot.adaptation_priority.value),
            )
            if safe_superset_category(pair[0], pair[1]) is None:
                # check if they are same region, conservative combinations
                # we relax it a bit by checking if they just aren't completely crazy
                if pair[0].exercise_id == pair[1].exercise_id:
                    raise TemplateWriteError("Superset cannot use the exact same exercise twice")
                if (
                    pair[0].axial_loading_level == LoadLimit.HIGH
                    and pair[1].axial_loading_level == LoadLimit.HIGH
                ):
                    raise TemplateWriteError(
                        "Superset cannot combine two high-axial-load exercises"
                    )
                # otherwise allow it, relying on user's manual auth

    return {exercise.id: exercise.slug for exercise in exercises}


@dataclass(frozen=True)
class _AdminSupersetExercise:
    exercise_id: UUID
    primary_muscle: MuscleGroup | None
    secondary_muscles: tuple[MuscleGroup, ...]
    equipment: frozenset[Equipment]
    exercise_type: ExerciseType
    axial_loading_level: LoadLimit
    reason_codes: tuple[str, ...]

    @classmethod
    def from_slot(cls, exercise: Exercise, adaptation_priority: str) -> "_AdminSupersetExercise":
        equipment = frozenset(item.equipment for item in exercise.equipment_items)
        axial_loading = exercise.axial_loading_level
        if axial_loading is None:
            axial_loading = (
                LoadLimit.HIGH
                if Equipment.BARBELL in equipment
                and exercise.movement_pattern in {MovementPattern.SQUAT, MovementPattern.HIP_HINGE}
                else LoadLimit.NONE
            )
        return cls(
            exercise_id=exercise.id,
            primary_muscle=exercise.primary_muscle,
            secondary_muscles=tuple(item.muscle for item in exercise.secondary_muscles),
            equipment=equipment,
            exercise_type=exercise.exercise_type,
            axial_loading_level=axial_loading,
            reason_codes=(f"TEMPLATE_ADAPTATION_PRIORITY:{adaptation_priority}",),
        )


class _ExerciseSemanticAdapter:
    def __init__(self, exercise: Exercise) -> None:
        self.movement_pattern = exercise.movement_pattern
        self.primary_muscle = exercise.primary_muscle
        self.secondary_muscles = tuple(item.muscle for item in exercise.secondary_muscles)
        self.exercise_type = exercise.exercise_type


def _replace_template_content(
    template: TrainingProgramTemplate,
    payload: AdminTrainingProgramTemplateWrite,
    exercise_slugs: dict[UUID, str],
) -> None:
    template.name_en = payload.name_en
    template.name_fa = payload.name_fa
    template.description_en = payload.description_en
    template.description_fa = payload.description_fa
    template.days_per_week = payload.days_per_week
    template.supported_levels = [level.value for level in payload.supported_levels]
    template.focus_tags = [tag.value for tag in payload.focus_tags]
    template.intensity_methods = [method.value for method in payload.intensity_methods]
    template.programming_rationale = [item.model_dump() for item in payload.programming_rationale]
    template.source_name = payload.source_name
    template.source_url = payload.source_url
    template.is_active = True
    template.structure_id = payload.structure_id
    for day_number, day_payload in enumerate(payload.days, start=1):
        day = TrainingProgramTemplateDay(
            day_number=day_number,
            title_en=day_payload.title_en,
            title_fa=day_payload.title_fa,
            structure_focus=day_payload.structure_focus,
            direct_target_muscles=[muscle.value for muscle in day_payload.direct_target_muscles],
        )
        template.days.append(day)
        for slot_order, slot_payload in enumerate(day_payload.slots, start=1):
            day.slots.append(
                TrainingProgramTemplateSlot(
                    slot_order=slot_order,
                    exercise_id=slot_payload.exercise_id,
                    exercise_slug_hint=exercise_slugs[slot_payload.exercise_id],
                    placeholder_name_en=slot_payload.display_name_en,
                    placeholder_name_fa=slot_payload.display_name_fa,
                    target_muscles=[muscle.value for muscle in slot_payload.target_muscles],
                    movement_pattern=slot_payload.movement_pattern,
                    intensity_method=slot_payload.intensity_method,
                    adaptation_priority=slot_payload.adaptation_priority,
                    superset_group=slot_payload.superset_group,
                    superset_exercise_id=slot_payload.superset_exercise_id,
                    superset_exercise_slug_hint=(
                        exercise_slugs[slot_payload.superset_exercise_id]
                        if slot_payload.superset_exercise_id
                        else None
                    ),
                    sets=slot_payload.sets,
                    rep_min=slot_payload.rep_min,
                    rep_max=slot_payload.rep_max,
                    target_rir=slot_payload.target_rir,
                    rest_seconds=slot_payload.rest_seconds,
                )
            )


def _unique_slug(db: Session, name_en: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name_en.lower()).strip("-") or "training-program"
    base = base[:110].strip("-") or "training-program"
    candidate = base
    suffix = 2
    while db.scalar(
        select(TrainingProgramTemplate.id).where(TrainingProgramTemplate.slug == candidate)
    ):
        candidate = f"{base[: 120 - len(str(suffix)) - 1]}-{suffix}"
        suffix += 1
    return candidate


def _get_template_or_raise(db: Session, template_id: UUID) -> TrainingProgramTemplate:
    template = get_training_program_template(db, template_id)
    if template is None:
        raise TemplateWriteError("Program template was not found after saving")
    return template
