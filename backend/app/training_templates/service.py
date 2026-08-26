from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete, func, inspect, or_, select
from sqlalchemy.orm import Session, selectinload

from app.exercises.enums import ExerciseContentType
from app.exercises.models import Exercise
from app.profile.enums import ExperienceLevel
from app.training_templates.catalog_invariants import validate_catalog_topology
from app.training_templates.models import (
    StructureFamily,
    TrainingProgramStructure,
    TrainingProgramTemplate,
    TrainingProgramTemplateDay,
    TrainingProgramTemplateSlot,
    TrainingTemplateCatalogState,
)
from app.training_templates.seed_data import (
    LEGACY_NOVICE_PRESCRIPTIONS,
    LEGACY_SOURCE_NAME,
    LEGACY_SOURCE_URL,
    NOVICE_DEFAULT_PRESCRIPTION,
    SOURCE_NAME,
    SOURCE_URL,
    TRAINING_PROGRAM_TEMPLATE_SEEDS,
    TemplateSlotSeed,
    TrainingProgramTemplateSeed,
)


@dataclass(frozen=True)
class TrainingTemplateSeedResult:
    templates: int
    linked_slots: int
    placeholder_slots: int


_CATALOG_STATE_KEY = "canonical"
_CATALOG_REVISION = 4


def seed_training_program_templates(db: Session) -> TrainingTemplateSeedResult:
    """Create the initial catalog once; normal reseeds preserve all Admin changes."""
    db.execute(
        delete(TrainingProgramTemplate).where(
            TrainingProgramTemplate.source_name == LEGACY_SOURCE_NAME,
            TrainingProgramTemplate.source_url == LEGACY_SOURCE_URL,
        )
    )
    db.flush()
    state = db.get(TrainingTemplateCatalogState, _CATALOG_STATE_KEY)
    if state is not None and state.catalog_revision >= _CATALOG_REVISION:
        db.commit()
        return _current_seed_result(db)

    _sync_canonical_catalog(db, replace_existing=state is not None)
    if state is None:
        db.add(
            TrainingTemplateCatalogState(
                key=_CATALOG_STATE_KEY,
                catalog_revision=_CATALOG_REVISION,
            )
        )
    else:
        state.catalog_revision = _CATALOG_REVISION
    db.commit()
    return _current_seed_result(db)


def upgrade_training_program_template_catalog(db: Session) -> TrainingTemplateSeedResult:
    """Explicitly replace the managed catalog with the current approved revision."""
    _sync_canonical_catalog(db, replace_existing=True)
    state = db.get(TrainingTemplateCatalogState, _CATALOG_STATE_KEY)
    if state is None:
        db.add(
            TrainingTemplateCatalogState(
                key=_CATALOG_STATE_KEY,
                catalog_revision=_CATALOG_REVISION,
            )
        )
    else:
        state.catalog_revision = _CATALOG_REVISION
    db.commit()
    return _current_seed_result(db)


def upgrade_novice_template_prescriptions(db: Session) -> int:
    """Update only untouched legacy novice prescriptions in the canonical catalog."""
    templates = list(
        db.scalars(
            select(TrainingProgramTemplate)
            .where(
                TrainingProgramTemplate.source_name == SOURCE_NAME,
                TrainingProgramTemplate.source_url == SOURCE_URL,
            )
            .options(
                selectinload(TrainingProgramTemplate.days).selectinload(
                    TrainingProgramTemplateDay.slots
                )
            )
        )
    )
    novice_levels = {ExperienceLevel.FIRST_MONTH.value, ExperienceLevel.BEGINNER.value}
    updated_slots = 0
    for template in templates:
        if not novice_levels.intersection(template.supported_levels):
            continue
        for day in template.days:
            for slot in day.slots:
                signature = (slot.sets, slot.rep_min, slot.rep_max)
                if signature not in LEGACY_NOVICE_PRESCRIPTIONS:
                    continue
                slot.sets, slot.rep_min, slot.rep_max = NOVICE_DEFAULT_PRESCRIPTION
                updated_slots += 1

    state = db.get(TrainingTemplateCatalogState, _CATALOG_STATE_KEY)
    if state is not None:
        state.catalog_revision = _CATALOG_REVISION
    db.flush()
    db.commit()
    return updated_slots


def _sync_canonical_catalog(db: Session, *, replace_existing: bool) -> None:
    for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        validate_catalog_topology(seed.days_per_week, seed.focus_tags)

    exercises_by_slug = {
        exercise.slug: exercise
        for exercise in db.scalars(
            select(Exercise).where(
                Exercise.content_type == ExerciseContentType.EXERCISE,
                Exercise.is_active.is_(True),
                Exercise.is_programmable.is_(True),
                or_(
                    Exercise.source.is_(None),
                    Exercise.source != "fitsho_training_template",
                ),
            )
        )
    }
    structure_ids_by_slug = _structure_ids_by_slug(db)
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
    seeded_slugs = {seed.slug for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS}
    if replace_existing:
        db.execute(
            delete(TrainingProgramTemplate).where(
                TrainingProgramTemplate.source_name == SOURCE_NAME,
                TrainingProgramTemplate.source_url == SOURCE_URL,
                TrainingProgramTemplate.slug.not_in(seeded_slugs),
            )
        )
    for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        template = templates_by_slug.get(seed.slug)
        if template is None:
            template = TrainingProgramTemplate(slug=seed.slug)
            db.add(template)
            templates_by_slug[seed.slug] = template
        elif replace_existing:
            template.days.clear()
            db.flush()
        else:
            continue

        _write_template(template, seed, exercises_by_slug, structure_ids_by_slug)

    db.flush()


def _write_template(
    template: TrainingProgramTemplate,
    seed: TrainingProgramTemplateSeed,
    exercises_by_slug: dict[str, Exercise],
    structure_ids_by_slug: dict[str, UUID],
) -> None:
    template.name_en = seed.name_en
    template.name_fa = seed.name_fa
    template.description_en = seed.description_en
    template.description_fa = seed.description_fa
    template.days_per_week = seed.days_per_week
    template.supported_levels = [level.value for level in seed.supported_levels]
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
    if seed.structure_slug:
        if structure_ids_by_slug and seed.structure_slug not in structure_ids_by_slug:
            raise ValueError(f"Missing TrainingProgramStructure for {seed.structure_slug}")
        template.structure_id = structure_ids_by_slug.get(seed.structure_slug)
    for day_number, day_seed in enumerate(seed.days, start=1):
        day = TrainingProgramTemplateDay(
            day_number=day_number,
            title_en=day_seed.title_en,
            title_fa=day_seed.title_fa,
            structure_focus=day_seed.structure_focus,
            direct_target_muscles=[muscle.value for muscle in day_seed.direct_target_muscles],
        )
        template.days.append(day)
        merged_slots: list[tuple[TemplateSlotSeed, TemplateSlotSeed | None]] = []
        superset_pending: dict[str, TemplateSlotSeed] = {}
        for slot_seed in day_seed.slots:
            if slot_seed.intensity_method.value == "superset" and slot_seed.superset_group:
                group = slot_seed.superset_group
                if group not in superset_pending:
                    superset_pending[group] = slot_seed
                else:
                    merged_slots.append((superset_pending.pop(group), slot_seed))
            else:
                merged_slots.append((slot_seed, None))

        for slot_order, (slot_seed, second_seed) in enumerate(merged_slots, start=1):
            exercise_id = _exercise_id_for_slot(slot_seed.catalog_slug_hints, exercises_by_slug)
            superset_exercise_id = None
            superset_exercise_slug_hint = None
            if second_seed is not None:
                superset_exercise_id = _exercise_id_for_slot(
                    second_seed.catalog_slug_hints, exercises_by_slug
                )
                superset_exercise_slug_hint = second_seed.exercise_slug_hint

            day.slots.append(
                TrainingProgramTemplateSlot(
                    slot_order=slot_order,
                    exercise_id=exercise_id,
                    exercise_slug_hint=slot_seed.exercise_slug_hint,
                    superset_exercise_id=superset_exercise_id,
                    superset_exercise_slug_hint=superset_exercise_slug_hint,
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


def _structure_ids_by_slug(db: Session) -> dict[str, UUID]:
    bind = db.get_bind()
    if not inspect(bind).has_table(TrainingProgramStructure.__tablename__):
        return {}
    return {
        structure.slug: structure.id
        for structure in db.scalars(
            select(TrainingProgramStructure).where(TrainingProgramStructure.is_active.is_(True))
        )
    }


def _current_seed_result(db: Session) -> TrainingTemplateSeedResult:
    seeded_slugs = tuple(seed.slug for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS)
    template_filter = TrainingProgramTemplate.slug.in_(seeded_slugs)
    templates = (
        db.scalar(
            select(func.count()).select_from(TrainingProgramTemplate).where(template_filter)
        )
        or 0
    )
    slot_statement = (
        select(func.count())
        .select_from(TrainingProgramTemplateSlot)
        .join(TrainingProgramTemplateDay)
        .join(TrainingProgramTemplate)
        .where(template_filter)
    )
    linked_slots = db.scalar(
        slot_statement.where(TrainingProgramTemplateSlot.exercise_id.is_not(None))
    ) or 0
    placeholder_slots = db.scalar(
        slot_statement.where(TrainingProgramTemplateSlot.exercise_id.is_(None))
    ) or 0
    return TrainingTemplateSeedResult(
        templates=templates,
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
    training_level: ExperienceLevel | None = None,
    family: StructureFamily | None = None,
    structure_id: UUID | None = None,
) -> list[TrainingProgramTemplate]:
    statement = (
        select(TrainingProgramTemplate)
        .where(TrainingProgramTemplate.is_active.is_(True))
        .options(
            selectinload(TrainingProgramTemplate.days)
            .selectinload(TrainingProgramTemplateDay.slots)
            .selectinload(TrainingProgramTemplateSlot.exercise),
            selectinload(TrainingProgramTemplate.days)
            .selectinload(TrainingProgramTemplateDay.slots)
            .selectinload(TrainingProgramTemplateSlot.superset_exercise),
        )
        .order_by(
            TrainingProgramTemplate.days_per_week.asc(),
            TrainingProgramTemplate.name_en.asc(),
        )
    )
    if days_per_week is not None:
        statement = statement.where(TrainingProgramTemplate.days_per_week == days_per_week)
    if family is not None:
        statement = statement.join(
            TrainingProgramStructure,
            TrainingProgramTemplate.structure_id == TrainingProgramStructure.id,
        ).where(TrainingProgramStructure.family == family)
    if structure_id is not None:
        statement = statement.where(TrainingProgramTemplate.structure_id == structure_id)
    templates = list(db.scalars(statement))
    if training_level is not None:
        templates = [
            template for template in templates if training_level.value in template.supported_levels
        ]
    return templates
