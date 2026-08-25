from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from app.exercises.enums import ExerciseContentType
from app.exercises.models import Exercise
from app.training_templates.models import (
    TrainingProgramTemplate,
    TrainingProgramTemplateDay,
    TrainingProgramTemplateSlot,
)
from app.training_templates.seed_data import (
    LEGACY_SOURCE_NAME,
    LEGACY_SOURCE_URL,
    SOURCE_NAME,
    SOURCE_URL,
    TRAINING_PROGRAM_TEMPLATE_SEEDS,
)


@dataclass(frozen=True)
class TrainingTemplateSeedResult:
    templates: int
    linked_slots: int
    placeholder_slots: int


def seed_training_program_templates(db: Session) -> TrainingTemplateSeedResult:
    db.execute(
        delete(TrainingProgramTemplate).where(
            TrainingProgramTemplate.source_name == LEGACY_SOURCE_NAME,
            TrainingProgramTemplate.source_url == LEGACY_SOURCE_URL,
        )
    )
    db.flush()
    exercises_by_slug = {
        exercise.slug: exercise
        for exercise in db.scalars(
            select(Exercise).where(
                Exercise.content_type == ExerciseContentType.EXERCISE,
                Exercise.is_active.is_(True),
                Exercise.is_programmable.is_(True),
                Exercise.source != "fitsho_training_template",
            )
        )
    }
    linked_slots = 0
    placeholder_slots = 0
    existing_templates = list(
        db.scalars(
            select(TrainingProgramTemplate).options(
                selectinload(TrainingProgramTemplate.days).selectinload(
                    TrainingProgramTemplateDay.slots
                )
            )
        )
    )
    templates_by_slug: dict[str, TrainingProgramTemplate] = {
        template.slug: template for template in existing_templates
    }
    for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        template = templates_by_slug.get(seed.slug)
        if template is None:
            template = TrainingProgramTemplate(slug=seed.slug)
            db.add(template)
            templates_by_slug[seed.slug] = template
        else:
            template.days.clear()

        template.name_en = seed.name_en
        template.name_fa = seed.name_fa
        template.description_en = seed.description_en
        template.description_fa = seed.description_fa
        template.days_per_week = seed.days_per_week
        template.training_level = seed.training_level
        template.fitness_goal = seed.fitness_goal
        template.focus_tags = [tag.value for tag in seed.focus_tags]
        template.intensity_methods = [method.value for method in seed.intensity_methods]
        template.programming_rationale = [
            {
                "title_en": rationale.title_en,
                "title_fa": rationale.title_fa,
                "detail_en": rationale.detail_en,
                "detail_fa": rationale.detail_fa,
            }
            for rationale in seed.programming_rationale
        ]
        template.source_name = SOURCE_NAME
        template.source_url = SOURCE_URL
        template.is_active = seed.is_active

    db.flush()

    for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        template = templates_by_slug[seed.slug]

        for day_number, day_seed in enumerate(seed.days, start=1):
            day = TrainingProgramTemplateDay(
                day_number=day_number,
                title_en=day_seed.title_en,
                title_fa=day_seed.title_fa,
                structure_focus=day_seed.structure_focus,
                direct_target_muscles=[muscle.value for muscle in day_seed.direct_target_muscles],
            )
            template.days.append(day)
            for slot_order, slot_seed in enumerate(day_seed.slots, start=1):
                exercise_id = _exercise_id_for_slot(slot_seed.catalog_slug_hints, exercises_by_slug)
                linked_slots += 1
                day.slots.append(
                    TrainingProgramTemplateSlot(
                        slot_order=slot_order,
                        exercise_id=exercise_id,
                        exercise_slug_hint=slot_seed.exercise_slug_hint,
                        placeholder_name_en=slot_seed.placeholder_name_en,
                        placeholder_name_fa=slot_seed.placeholder_name_fa,
                        target_muscles=[muscle.value for muscle in slot_seed.target_muscles],
                        movement_pattern=slot_seed.movement_pattern,
                        intensity_method=slot_seed.intensity_method,
                        adaptation_priority=slot_seed.adaptation_priority,
                        superset_group=slot_seed.superset_group,
                        sets=slot_seed.sets,
                        rep_min=slot_seed.rep_min,
                        rep_max=slot_seed.rep_max,
                        target_rir=slot_seed.target_rir,
                        rest_seconds=slot_seed.rest_seconds,
                    )
                )

    db.commit()
    return TrainingTemplateSeedResult(
        templates=len(TRAINING_PROGRAM_TEMPLATE_SEEDS),
        linked_slots=linked_slots,
        placeholder_slots=placeholder_slots,
    )


def _exercise_id_for_slot(
    candidate_slugs: tuple[str, ...],
    exercises_by_slug: dict[str, Exercise],
) -> UUID | None:
    for candidate_slug in candidate_slugs:
        exercise = exercises_by_slug.get(candidate_slug)
        if exercise is not None and exercise.content_type is ExerciseContentType.EXERCISE:
            return exercise.id
    raise ValueError(
        "Missing active programmable Exercise Library movement for template slot: "
        + ", ".join(candidate_slugs)
    )


def list_training_program_templates(
    db: Session,
    *,
    days_per_week: int | None = None,
) -> list[TrainingProgramTemplate]:
    statement = (
        select(TrainingProgramTemplate)
        .where(TrainingProgramTemplate.is_active.is_(True))
        .options(
            selectinload(TrainingProgramTemplate.days)
            .selectinload(TrainingProgramTemplateDay.slots)
            .selectinload(TrainingProgramTemplateSlot.exercise)
        )
        .order_by(
            TrainingProgramTemplate.days_per_week.asc(),
            TrainingProgramTemplate.training_level.asc(),
            TrainingProgramTemplate.name_en.asc(),
        )
    )
    if days_per_week is not None:
        statement = statement.where(TrainingProgramTemplate.days_per_week == days_per_week)
    return list(db.scalars(statement))
