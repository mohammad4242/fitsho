import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.admin.schemas import AdminTrainingProgramTemplateWrite
from app.exercises.models import Exercise
from app.training_templates.models import (
    TrainingProgramTemplate,
    TrainingProgramTemplateDay,
    TrainingProgramTemplateSlot,
)


class TemplateWriteError(ValueError):
    pass


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
            .selectinload(TrainingProgramTemplateSlot.exercise)
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


def _validate_exercise_links(
    db: Session,
    payload: AdminTrainingProgramTemplateWrite,
) -> dict[UUID, str]:
    exercise_ids = {slot.exercise_id for day in payload.days for slot in day.slots}
    exercises = list(
        db.scalars(
            select(Exercise).where(
                Exercise.id.in_(exercise_ids),
                Exercise.is_active.is_(True),
            )
        )
    )
    active_exercise_ids = {exercise.id for exercise in exercises}
    if inactive_or_unknown := exercise_ids - active_exercise_ids:
        formatted_ids = ", ".join(sorted(str(item) for item in inactive_or_unknown))
        raise TemplateWriteError(f"Selected exercise is missing or inactive: {formatted_ids}")
    return {exercise.id: exercise.slug for exercise in exercises}


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
    template.training_level = payload.training_level
    template.fitness_goal = payload.fitness_goal
    template.focus_tags = payload.focus_tags
    template.intensity_methods = [method.value for method in payload.intensity_methods]
    template.programming_rationale = [item.model_dump() for item in payload.programming_rationale]
    template.source_name = payload.source_name
    template.source_url = payload.source_url
    template.is_active = True
    for day_number, day_payload in enumerate(payload.days, start=1):
        day = TrainingProgramTemplateDay(
            day_number=day_number,
            title_en=day_payload.title_en,
            title_fa=day_payload.title_fa,
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
