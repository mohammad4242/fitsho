from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.exercises.enums import MuscleGroup
from app.training_templates.engine_reference import load_template_references
from app.training_templates.models import (
    TrainingProgramTemplate,
    TrainingProgramTemplateCategory,
    TrainingProgramTemplateDay,
)
from app.training_templates.seed_data import TRAINING_PROGRAM_TEMPLATE_SEEDS
from app.training_templates.service import seed_training_program_templates
from tests.training_templates.catalog_fixture import seed_real_catalog_exercises

SUPPLEMENTAL_DIRECT_MUSCLES = {
    MuscleGroup.ABS,
    MuscleGroup.OBLIQUES,
    MuscleGroup.LOWER_BACK,
    MuscleGroup.ABDUCTORS,
    MuscleGroup.ADDUCTORS,
    MuscleGroup.FOREARMS,
}


def test_active_4_5_6_day_intermediate_advanced_slots_stay_inside_direct_scope() -> None:
    audited = 0
    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        levels = {level.value for level in template.supported_levels}
        if (
            not template.is_active
            or template.days_per_week not in {4, 5, 6}
            or not levels.intersection({"intermediate", "advanced"})
        ):
            continue
        audited += 1
        for day in template.days:
            allowed = set(day.direct_target_muscles)
            for slot in day.slots:
                if not slot.target_muscles:
                    continue
                for target_muscle in slot.target_muscles:
                    if target_muscle in SUPPLEMENTAL_DIRECT_MUSCLES:
                        continue
                    assert target_muscle in allowed, (
                        template.slug,
                        day.title_en,
                        slot.exercise_slug_hint,
                        target_muscle,
                    )
    assert audited == 36


def test_specialized_five_day_metadata_is_exact_not_generic_upper() -> None:
    seeds = {seed.slug: seed for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS}
    expected = {
        "p30-5-day-upper-priority-iranian-intermediate": (
            {MuscleGroup.CHEST, MuscleGroup.TRICEPS},
            {MuscleGroup.SHOULDERS, MuscleGroup.BICEPS},
            None,
            {MuscleGroup.CHEST, MuscleGroup.BICEPS},
            {MuscleGroup.BACK},
        ),
        "p34-5-day-fst7-arms-priority-intermediate": (
            {MuscleGroup.CHEST, MuscleGroup.BICEPS},
            {MuscleGroup.BACK, MuscleGroup.TRICEPS},
            None,
            {MuscleGroup.SHOULDERS, MuscleGroup.TRAPS, MuscleGroup.CALVES},
            {MuscleGroup.BICEPS, MuscleGroup.TRICEPS},
        ),
        "p36-5-day-professional-compound-intermediate": (
            {MuscleGroup.CHEST, MuscleGroup.TRICEPS},
            None,
            {MuscleGroup.BACK, MuscleGroup.BICEPS},
            {MuscleGroup.SHOULDERS, MuscleGroup.TRAPS},
            None,
        ),
    }
    for slug, day_scopes in expected.items():
        for day, expected_scope in zip(seeds[slug].days, day_scopes, strict=True):
            if expected_scope is not None:
                assert set(day.direct_target_muscles) == expected_scope


def test_iranmuscle_day_four_keeps_rdl_inside_declared_scope() -> None:
    seeds = {seed.slug: seed for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS}
    day = seeds["p50-4-day-iranmuscle-intermediate"].days[3]
    assert set(day.direct_target_muscles) == {MuscleGroup.SHOULDERS, MuscleGroup.HAMSTRINGS}
    rdl = next(slot for slot in day.slots if "deadlift" in slot.exercise_slug_hint)
    assert rdl.target_muscles == (MuscleGroup.HAMSTRINGS,)


def test_legitimate_upper_lower_full_body_metadata_remains_broad() -> None:
    seeds = {seed.slug: seed for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS}
    template = seeds["p40-6-day-upper-lower-x3-intermediate"]
    for day in template.days:
        muscles = set(day.direct_target_muscles)
        if day.structure_focus == "upper":
            assert {MuscleGroup.CHEST, MuscleGroup.BACK, MuscleGroup.SHOULDERS} <= muscles
        else:
            assert {
                MuscleGroup.QUADRICEPS,
                MuscleGroup.HAMSTRINGS,
                MuscleGroup.GLUTES,
            } <= muscles


def test_active_catalog_metadata_and_slot_order_match_canonical_seed(db: Session) -> None:
    seed_real_catalog_exercises(db)
    seed_training_program_templates(db)
    seeds = {seed.slug: seed for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS}
    references = load_template_references(db)
    templates = db.scalars(
        select(TrainingProgramTemplate)
        .where(
            TrainingProgramTemplate.is_active.is_(True),
            TrainingProgramTemplate.category == TrainingProgramTemplateCategory.GENERIC,
        )
        .options(
            selectinload(TrainingProgramTemplate.days).selectinload(
                TrainingProgramTemplateDay.slots
            )
        )
    ).all()

    assert len(references) == len(TRAINING_PROGRAM_TEMPLATE_SEEDS) == len(templates)
    templates_by_slug = {template.slug: template for template in templates}
    for reference in references:
        seed = seeds[reference.slug]
        persisted = templates_by_slug[reference.slug]
        for day, seed_day in zip(reference.days, seed.days, strict=True):
            assert day.focus == seed_day.direct_target_muscles
            persisted_day = next(
                item for item in persisted.days if item.day_number == day.day_number
            )
            orders = sorted(slot.slot_order for slot in persisted_day.slots)
            assert orders == list(range(1, len(orders) + 1))
            seed_slots = {slot.exercise_slug_hint: slot for slot in seed_day.slots}
            for slot in day.slots:
                assert slot.exercise_slug_hint in seed_slots
                assert slot.target_muscles == seed_slots[slot.exercise_slug_hint].target_muscles
