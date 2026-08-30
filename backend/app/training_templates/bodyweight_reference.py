from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.profile.enums import ExperienceLevel
from app.training_templates.models import (
    TrainingProgramTemplate,
    TrainingProgramTemplateCategory,
    TrainingProgramTemplateDay,
    TrainingProgramTemplateSlot,
)
from app.workouts.bodyweight_templates import (
    BodyweightProgramTemplate,
    BodyweightTemplateDay,
    BodyweightTemplateExercise,
    get_bodyweight_template,
)
from app.workouts.program_engine.enums import SplitType


def load_bodyweight_template(
    db: Session,
    experience_level: ExperienceLevel,
    days_per_week: int,
) -> BodyweightProgramTemplate | None:
    canonical = get_bodyweight_template(experience_level, days_per_week)
    if canonical is None:
        return None
    template = db.scalar(
        select(TrainingProgramTemplate)
        .where(
            TrainingProgramTemplate.slug == canonical.slug,
            TrainingProgramTemplate.category == TrainingProgramTemplateCategory.BODYWEIGHT_FIXED,
            TrainingProgramTemplate.engine_eligible.is_(False),
            TrainingProgramTemplate.is_active.is_(True),
            TrainingProgramTemplate.days_per_week == days_per_week,
        )
        .options(
            selectinload(TrainingProgramTemplate.days).selectinload(
                TrainingProgramTemplateDay.slots
            )
        )
    )
    if template is None:
        return canonical
    return _to_bodyweight_template(template, experience_level)


def _to_bodyweight_template(
    template: TrainingProgramTemplate,
    experience_level: ExperienceLevel,
) -> BodyweightProgramTemplate:
    return BodyweightProgramTemplate(
        slug=template.slug,
        experience_level=experience_level,
        days_per_week=template.days_per_week,
        split_type=(SplitType.UPPER_LOWER if template.days_per_week == 4 else SplitType.FULL_BODY),
        days=tuple(
            BodyweightTemplateDay(
                day_number=day.day_number,
                title_en=day.title_en,
                title_fa=day.title_fa,
                exercises=tuple(_to_bodyweight_exercise(slot) for slot in day.slots),
            )
            for day in template.days
        ),
    )


def _to_bodyweight_exercise(
    slot: TrainingProgramTemplateSlot,
) -> BodyweightTemplateExercise:
    if slot.prescription_mode.value == "duration":
        return BodyweightTemplateExercise(
            exercise_slug=slot.exercise_slug_hint,
            sets=slot.sets,
            rest_seconds=slot.rest_seconds,
            duration_min_seconds=slot.duration_min_seconds,
            duration_max_seconds=slot.duration_max_seconds,
        )
    return BodyweightTemplateExercise(
        exercise_slug=slot.exercise_slug_hint,
        sets=slot.sets,
        rest_seconds=slot.rest_seconds,
        rep_min=slot.rep_min,
        rep_max=slot.rep_max,
        target_rir=slot.target_rir,
    )
