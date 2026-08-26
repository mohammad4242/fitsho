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
from app.training_templates.seed_data import (
    CANONICAL_TEMPLATE_DEFINITIONS,
    LEGACY_SOURCE_NAME,
    LEGACY_SOURCE_URL,
    SOURCE_NAME,
    SOURCE_URL,
    TRAINING_PROGRAM_TEMPLATE_SEEDS,
)
from app.training_templates.service import seed_training_program_templates
from tests.training_templates.catalog_fixture import seed_real_catalog_exercises


def test_seed_adds_exactly_49_level_specific_canonical_templates(db: Session) -> None:
    seed_real_catalog_exercises(db)

    result = seed_training_program_templates(db)

    assert len(CANONICAL_TEMPLATE_DEFINITIONS) == 49
    assert result.templates == 49
    assert db.scalar(select(func.count()).select_from(TrainingProgramTemplate)) == 49
    assert {template.days_per_week for template in db.scalars(select(TrainingProgramTemplate))} == {
        2,
        3,
        4,
        5,
        6,
    }


def test_seed_has_approved_supported_levels_and_day_counts() -> None:
    expected_levels = {
        definition.canonical_slug: set(definition.supported_levels)
        for definition in CANONICAL_TEMPLATE_DEFINITIONS
    }

    assert len(TRAINING_PROGRAM_TEMPLATE_SEEDS) == 49
    for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        assert set(seed.supported_levels) == expected_levels[seed.canonical_slug]
        assert len(seed.supported_levels) == len(set(seed.supported_levels))
        assert seed.slug == seed.canonical_slug
        assert seed.days_per_week == len(
            next(
                definition.days
                for definition in CANONICAL_TEMPLATE_DEFINITIONS
                if definition.canonical_slug == seed.canonical_slug
            )
        )
        minimum_slots = 4 if seed.days_per_week <= 4 else 3
        assert all(minimum_slots <= len(day.slots) <= 9 for day in seed.days)


def test_canonical_template_builder_excludes_lever_seated_crunch() -> None:
    crunch_slug = "fedb-1452-lever-seated-crunch"

    assert all(
        crunch_slug not in (slot.exercise_slug_hint, *slot.catalog_slug_hints)
        for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS
        for day in seed.days
        for slot in day.slots
    )


def test_seed_uses_real_active_programmable_exercise_rows_only(db: Session) -> None:
    seed_real_catalog_exercises(db)

    result = seed_training_program_templates(db)

    slots = list(db.scalars(select(TrainingProgramTemplateSlot)))
    assert result.linked_slots == len(slots)
    assert result.placeholder_slots == 0
    assert all(slot.exercise_id is not None for slot in slots)
    assert all(
        slot.placeholder_name_en is None and slot.placeholder_name_fa is None for slot in slots
    )
    assert all(
        slot.exercise is not None
        and slot.exercise.content_type is ExerciseContentType.EXERCISE
        and slot.exercise.is_active
        and slot.exercise.is_programmable
        and slot.exercise.source != "fitsho_training_template"
        for slot in slots
    )


def test_seed_persists_five_bilingual_guidance_items_per_template() -> None:
    for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        assert len(seed.programming_rationale) == 5
        assert all(
            item.title_en and item.title_fa and item.detail_en and item.detail_fa
            for item in seed.programming_rationale
        )


def test_seed_is_idempotent_without_duplicate_rows_or_days(db: Session) -> None:
    seed_real_catalog_exercises(db)

    first = seed_training_program_templates(db)
    second = seed_training_program_templates(db)

    assert first == second
    assert db.scalar(select(func.count()).select_from(TrainingProgramTemplate)) == 49
    assert (
        db.scalar(select(func.count()).select_from(TrainingProgramTemplateSlot))
        == first.linked_slots
    )


def test_seed_physically_deletes_legacy_source_rows_and_keeps_custom_templates(
    db: Session,
) -> None:
    seed_real_catalog_exercises(db)
    legacy = [
        TrainingProgramTemplate(
            slug=f"legacy-fitsho-template-{index}",
            name_en="Legacy Fitsho Template",
            name_fa="قالب قدیمی فیتشو",
            description_en="Legacy catalog row.",
            description_fa="ردیف قدیمی کاتالوگ.",
            days_per_week=2,
            supported_levels=[ExperienceLevel.BEGINNER.value],
            focus_tags=["full_body"],
            intensity_methods=["standard"],
            programming_rationale=[],
            source_name=LEGACY_SOURCE_NAME,
            source_url=LEGACY_SOURCE_URL,
            is_active=True,
        )
        for index in range(3)
    ]
    custom = TrainingProgramTemplate(
        slug="admin-custom-template",
        name_en="Admin Custom Template",
        name_fa="قالب سفارشی ادمین",
        description_en="Custom template.",
        description_fa="قالب سفارشی.",
        days_per_week=2,
        supported_levels=[ExperienceLevel.BEGINNER.value],
        focus_tags=["full_body"],
        intensity_methods=["standard"],
        programming_rationale=[],
        source_name="Fitsho admin library",
        source_url="https://fitsho.local/admin-library",
        is_active=True,
    )
    db.add_all([*legacy, custom])
    db.commit()

    seed_training_program_templates(db)

    assert (
        db.scalar(
            select(func.count())
            .select_from(TrainingProgramTemplate)
            .where(
                TrainingProgramTemplate.source_name == LEGACY_SOURCE_NAME,
                TrainingProgramTemplate.source_url == LEGACY_SOURCE_URL,
            )
        )
        == 0
    )
    assert (
        db.scalar(
            select(TrainingProgramTemplate).where(TrainingProgramTemplate.slug == custom.slug)
        )
        is not None
    )
    assert (
        db.scalar(
            select(func.count())
            .select_from(TrainingProgramTemplate)
            .where(TrainingProgramTemplate.source_name == SOURCE_NAME)
        )
        == 49
    )
    assert SOURCE_URL == "https://fitsho.local/training-template-catalog"


def test_seed_fails_when_a_required_real_library_movement_is_missing(db: Session) -> None:
    seed_real_catalog_exercises(db, slugs=[])

    try:
        seed_training_program_templates(db)
    except ValueError as exc:
        assert "Missing active programmable Exercise Library movement" in str(exc)
    else:
        raise AssertionError("catalog seed must reject missing real Exercise Library movements")


def test_seed_does_not_change_the_exercise_library_rows(db: Session) -> None:
    seed_real_catalog_exercises(db)
    before = db.scalar(select(func.count()).select_from(Exercise))

    seed_training_program_templates(db)

    assert db.scalar(select(func.count()).select_from(Exercise)) == before


def _seeded_template_with_content(db: Session, slug: str) -> TrainingProgramTemplate | None:
    return db.scalar(
        select(TrainingProgramTemplate)
        .where(TrainingProgramTemplate.slug == slug)
        .options(
            selectinload(TrainingProgramTemplate.days).selectinload(
                TrainingProgramTemplateDay.slots
            )
        )
    )


def test_normal_seed_preserves_admin_template_edit(db: Session) -> None:
    seed_real_catalog_exercises(db)
    seed_training_program_templates(db)
    template = _seeded_template_with_content(db, "p01-2-day-full-body-ab-first-month")
    assert template is not None
    template.name_en = "Admin-owned edit"
    template.days[0].slots[0].rep_max = 15
    db.commit()

    seed_training_program_templates(db)

    refreshed = _seeded_template_with_content(db, template.slug)
    assert refreshed is not None
    assert refreshed.name_en == "Admin-owned edit"
    assert refreshed.days[0].slots[0].rep_max == 15


def test_normal_seed_preserves_admin_slot_removal(db: Session) -> None:
    seed_real_catalog_exercises(db)
    seed_training_program_templates(db)
    template = _seeded_template_with_content(db, "p01-2-day-full-body-ab-first-month")
    assert template is not None
    original_count = len(template.days[0].slots)
    template.days[0].slots.pop()
    db.commit()

    seed_training_program_templates(db)

    refreshed = _seeded_template_with_content(db, template.slug)
    assert refreshed is not None
    assert len(refreshed.days[0].slots) == original_count - 1


def test_normal_seed_does_not_recreate_physically_deleted_canonical_template(db: Session) -> None:
    seed_real_catalog_exercises(db)
    seed_training_program_templates(db)
    template = _seeded_template_with_content(db, "p01-2-day-full-body-ab-first-month")
    assert template is not None
    db.delete(template)
    db.commit()

    seed_training_program_templates(db)

    assert _seeded_template_with_content(db, "p01-2-day-full-body-ab-first-month") is None


def test_normal_seed_preserves_disabled_canonical_template(db: Session) -> None:
    seed_real_catalog_exercises(db)
    seed_training_program_templates(db)
    template = _seeded_template_with_content(db, "p01-2-day-full-body-ab-first-month")
    assert template is not None
    template.is_active = False
    db.commit()

    seed_training_program_templates(db)

    refreshed = _seeded_template_with_content(db, template.slug)
    assert refreshed is not None
    assert refreshed.is_active is False
