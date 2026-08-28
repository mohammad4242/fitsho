from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.exercises.enums import ExerciseContentType
from app.exercises.models import Exercise
from app.profile.enums import ExperienceLevel
from app.training_templates.models import (
    TrainingProgramTemplate,
    TrainingProgramTemplateDay,
    TrainingProgramTemplateSlot,
)
from app.training_templates.seed_data import TRAINING_PROGRAM_TEMPLATE_SEEDS
from app.training_templates.service import (
    list_training_program_templates,
    seed_training_program_templates,
)
from tests.training_templates.catalog_fixture import seed_real_catalog_exercises

BRANDED_TEMPLATE_SLUGS = (
    "p50-4-day-iranmuscle-intermediate",
    "p51-4-day-gymextreme-advanced",
    "p52-4-day-arnoldsho-advanced",
    "p53-4-day-aloplay-intermediate",
)


def _day(title_fa: str, *exercise_slugs: str) -> tuple[str, tuple[str, ...]]:
    return title_fa, exercise_slugs


EXPECTED_BRANDED_TEMPLATES = {
    "p50-4-day-iranmuscle-intermediate": (
        "ایران ماسل - برنامه ۴ روزه متوسط",
        "IRANMUSCLE 4-Day Intermediate",
        ExperienceLevel.INTERMEDIATE,
        (
            _day(
                "جلو پا + ساق",
                "fedb-1435-barbell-back-squat",
                "fedb-2611-lever-horizontal-leg-press",
                "fedb-0585-lever-leg-extension",
                "fedb-0605-lever-standing-calf-raise",
            ),
            _day(
                "سینه + پشت بازو",
                "fedb-0025-barbell-bench-press",
                "fedb-0314-dumbbell-incline-bench-press",
                "fedb-1269-cable-standing-fly",
                "fedb-1723-cable-triceps-pushdown",
                "fedb-0194-cable-rope-overhead-triceps-extension",
            ),
            _day(
                "پشت + جلو بازو",
                "owner-e0c26a271aac-barbell-bent-over-row",
                "fedb-0974-cable-close-grip-lat-pulldown",
                "owner-2a5de4dc7ba3-seated-cable-row",
                "fedb-0031-barbell-curl",
                "fedb-0285-seated-alternating-dumbbell-curl",
            ),
            _day(
                "سرشانه + پشت پا",
                "fedb-0553-military-press",
                "fedb-0178-cable-lateral-raise",
                "fedb-0602-lever-seated-reverse-fly",
                "fedb-0300-dumbbell-deadlift",
                "fedb-0586-lever-lying-leg-curl",
            ),
        ),
    ),
    "p51-4-day-gymextreme-advanced": (
        "جیم اکستریم - برنامه ۴ روزه پیشرفته",
        "GymExtreme 4-Day Advanced",
        ExperienceLevel.ADVANCED,
        (
            _day(
                "پا با تأکید چهارسر",
                "fedb-1435-barbell-back-squat",
                "fedb-0336-dumbbell-lunge",
                "fedb-2611-lever-horizontal-leg-press",
                "fedb-0585-lever-leg-extension",
                "fedb-0599-lever-seated-leg-curl",
                "fedb-0605-lever-standing-calf-raise",
            ),
            _day(
                "سینه + سرشانه",
                "fedb-0025-barbell-bench-press",
                "fedb-0314-dumbbell-incline-bench-press",
                "fedb-1269-cable-standing-fly",
                "fedb-0553-military-press",
                "fedb-0178-cable-lateral-raise",
                "fedb-0602-lever-seated-reverse-fly",
            ),
            _day(
                "پشت + جلو بازو + پشت بازو",
                "owner-e0c26a271aac-barbell-bent-over-row",
                "fedb-0974-cable-close-grip-lat-pulldown",
                "owner-2a5de4dc7ba3-seated-cable-row",
                "fedb-0229-cable-standing-inner-curl",
                "fedb-0200-cable-rope-triceps-pushdown",
                "fedb-0298-dumbbell-cross-body-hammer-curl",
                "fedb-0194-cable-rope-overhead-triceps-extension",
            ),
            _day(
                "پشت پا + زنجیره خلفی",
                "fedb-0300-dumbbell-deadlift",
                "fedb-0586-lever-lying-leg-curl",
                "fedb-0668-rear-decline-bridge",
                "fedb-0336-dumbbell-lunge",
                "fedb-0605-lever-standing-calf-raise",
            ),
        ),
    ),
    "p52-4-day-arnoldsho-advanced": (
        "آرنولدشو - برنامه ۴ روزه پیشرفته",
        "Arnoldsho 4-Day Advanced",
        ExperienceLevel.ADVANCED,
        (
            _day(
                "سینه + پشت بازو",
                "fedb-0025-barbell-bench-press",
                "fedb-0314-dumbbell-incline-bench-press",
                "fedb-1269-cable-standing-fly",
                "fedb-1723-cable-triceps-pushdown",
                "fedb-0194-cable-rope-overhead-triceps-extension",
            ),
            _day(
                "پشت + جلو بازو",
                "owner-e0c26a271aac-barbell-bent-over-row",
                "fedb-0974-cable-close-grip-lat-pulldown",
                "owner-2a5de4dc7ba3-seated-cable-row",
                "fedb-0238-cable-straight-arm-pulldown",
                "fedb-0031-barbell-curl",
                "fedb-0592-lever-preacher-curl",
            ),
            _day(
                "سرشانه + کول",
                "fedb-0553-military-press",
                "fedb-0178-cable-lateral-raise",
                "fedb-0602-lever-seated-reverse-fly",
                "fedb-0095-barbell-shrug",
            ),
            _day(
                "پا",
                "fedb-1435-barbell-back-squat",
                "fedb-0585-lever-leg-extension",
                "fedb-0599-lever-seated-leg-curl",
                "fedb-2611-lever-horizontal-leg-press",
                "fedb-0605-lever-standing-calf-raise",
            ),
        ),
    ),
    "p53-4-day-aloplay-intermediate": (
        "الوپلی - برنامه ۴ روزه متوسط",
        "Aloplay 4-Day Intermediate",
        ExperienceLevel.INTERMEDIATE,
        (
            _day(
                "سینه + پشت بازو",
                "fedb-0025-barbell-bench-press",
                "fedb-0314-dumbbell-incline-bench-press",
                "fedb-1269-cable-standing-fly",
                "fedb-1723-cable-triceps-pushdown",
                "fedb-0194-cable-rope-overhead-triceps-extension",
            ),
            _day(
                "پا",
                "fedb-1435-barbell-back-squat",
                "fedb-2611-lever-horizontal-leg-press",
                "fedb-0585-lever-leg-extension",
                "fedb-0586-lever-lying-leg-curl",
                "fedb-0605-lever-standing-calf-raise",
            ),
            _day(
                "پشت + جلو بازو",
                "owner-e0c26a271aac-barbell-bent-over-row",
                "fedb-0974-cable-close-grip-lat-pulldown",
                "owner-2a5de4dc7ba3-seated-cable-row",
                "fedb-0031-barbell-curl",
                "fedb-0285-seated-alternating-dumbbell-curl",
            ),
            _day(
                "سرشانه + شکم",
                "fedb-0553-military-press",
                "fedb-0178-cable-lateral-raise",
                "fedb-0095-barbell-shrug",
                "fedb-0464-front-plank",
                "fedb-0705-side-plank",
            ),
        ),
    ),
}


def test_four_branded_templates_have_exact_names_levels_and_ordered_exercise_slugs() -> None:
    seeds = {seed.slug: seed for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS}

    assert tuple(slug for slug in seeds if slug in BRANDED_TEMPLATE_SLUGS) == BRANDED_TEMPLATE_SLUGS
    for slug, (name_fa, name_en, level, expected_days) in EXPECTED_BRANDED_TEMPLATES.items():
        seed = seeds[slug]
        assert seed.name_fa == name_fa
        assert seed.name_en == name_en
        assert seed.supported_levels == (level,)
        assert seed.days_per_week == 4
        assert (
            tuple(
                (day.title_fa, tuple(slot.exercise_slug_hint for slot in day.slots))
                for day in seed.days
            )
            == expected_days
        )


def test_four_branded_templates_seed_to_real_exercises_without_placeholders_or_new_exercises(
    db: Session,
) -> None:
    seed_real_catalog_exercises(db)
    exercise_count_before = db.scalar(select(func.count()).select_from(Exercise))

    result = seed_training_program_templates(db)
    templates = list(
        db.scalars(
            select(TrainingProgramTemplate)
            .where(TrainingProgramTemplate.slug.in_(BRANDED_TEMPLATE_SLUGS))
            .options(
                selectinload(TrainingProgramTemplate.days)
                .selectinload(TrainingProgramTemplateDay.slots)
                .selectinload(TrainingProgramTemplateSlot.exercise)
            )
        )
    )

    assert {template.slug for template in templates} == set(BRANDED_TEMPLATE_SLUGS)
    assert all(len(template.days) == 4 for template in templates)
    assert result.placeholder_slots == 0
    slots = [slot for template in templates for day in template.days for slot in day.slots]
    assert len(slots) == 83
    assert all(
        slot.exercise_id is not None
        and slot.placeholder_name_en is None
        and slot.placeholder_name_fa is None
        and slot.exercise is not None
        and slot.exercise.content_type is ExerciseContentType.EXERCISE
        and slot.exercise.is_active
        and slot.exercise.is_programmable
        and slot.exercise.source != "fitsho_training_template"
        for slot in slots
    )
    assert db.scalar(select(func.count()).select_from(Exercise)) == exercise_count_before

    listed_slugs = {template.slug for template in list_training_program_templates(db)}
    assert set(BRANDED_TEMPLATE_SLUGS).issubset(listed_slugs)
    assert {
        "p01-2-day-full-body-ab-first-month",
        "p25-4-day-push-pull-quads-posterior-advanced",
    }.issubset(listed_slugs)


def test_four_branded_templates_are_idempotent_and_keep_zero_placeholders(db: Session) -> None:
    seed_real_catalog_exercises(db)

    first = seed_training_program_templates(db)
    first_counts = (
        db.scalar(
            select(func.count())
            .select_from(TrainingProgramTemplate)
            .where(TrainingProgramTemplate.slug.in_(BRANDED_TEMPLATE_SLUGS))
        ),
        db.scalar(
            select(func.count())
            .select_from(TrainingProgramTemplateSlot)
            .join(TrainingProgramTemplateDay)
            .join(TrainingProgramTemplate)
            .where(TrainingProgramTemplate.slug.in_(BRANDED_TEMPLATE_SLUGS))
        ),
    )

    second = seed_training_program_templates(db)
    second_counts = (
        db.scalar(
            select(func.count())
            .select_from(TrainingProgramTemplate)
            .where(TrainingProgramTemplate.slug.in_(BRANDED_TEMPLATE_SLUGS))
        ),
        db.scalar(
            select(func.count())
            .select_from(TrainingProgramTemplateSlot)
            .join(TrainingProgramTemplateDay)
            .join(TrainingProgramTemplate)
            .where(TrainingProgramTemplate.slug.in_(BRANDED_TEMPLATE_SLUGS))
        ),
    )

    assert second == first
    assert first.placeholder_slots == 0
    assert second.placeholder_slots == 0
    assert second_counts == first_counts == (4, 83)
