from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.exercises.enums import MuscleGroup
from app.training_templates.models import (
    TrainingProgramTemplate,
    TrainingProgramTemplateDay,
    TrainingProgramTemplateSlot,
)
from app.training_templates.tags import validate_template_focus_tags
from app.workouts.program_engine.schemas import (
    TemplateReference,
    TemplateReferenceDay,
    TemplateReferenceSlot,
)


def load_template_references(db: Session) -> tuple[TemplateReference, ...]:
    templates = db.scalars(
        select(TrainingProgramTemplate)
        .where(TrainingProgramTemplate.is_active.is_(True))
        .options(
            selectinload(TrainingProgramTemplate.days).selectinload(
                TrainingProgramTemplateDay.slots
            )
        )
        .order_by(
            TrainingProgramTemplate.days_per_week,
            TrainingProgramTemplate.training_level,
            TrainingProgramTemplate.slug,
        )
    )
    return tuple(_reference(template) for template in templates)


def _reference(template: TrainingProgramTemplate) -> TemplateReference:
    return TemplateReference(
        slug=template.slug,
        days_per_week=template.days_per_week,
        training_level=template.training_level.value,
        fitness_goal=template.fitness_goal.value,
        focus_tags=validate_template_focus_tags(
            template.focus_tags,
            intensity_methods=template.intensity_methods,
            days=template.days,
        ),
        intensity_methods=tuple(template.intensity_methods),
        days=tuple(
            TemplateReferenceDay(
                day_number=day.day_number,
                title=day.title_en,
                title_fa=day.title_fa,
                focus=tuple(MuscleGroup(muscle) for muscle in day.direct_target_muscles),
                slots=tuple(_slot_reference(slot) for slot in day.slots),
                structure_focus=day.structure_focus,
            )
            for day in template.days
        ),
    )


def _slot_reference(slot: TrainingProgramTemplateSlot) -> TemplateReferenceSlot:
    return TemplateReferenceSlot(
        exercise_id=slot.exercise_id,
        exercise_slug_hint=slot.exercise_slug_hint,
        target_muscles=tuple(MuscleGroup(muscle) for muscle in slot.target_muscles),
        movement_pattern=slot.movement_pattern,
        intensity_method=slot.intensity_method.value,
        adaptation_priority=slot.adaptation_priority.value,
        superset_group=slot.superset_group,
        sets=slot.sets,
        rep_min=slot.rep_min,
        rep_max=slot.rep_max,
        target_rir=slot.target_rir,
        rest_seconds=slot.rest_seconds,
    )
