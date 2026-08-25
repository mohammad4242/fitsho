from __future__ import annotations

from collections.abc import Iterable

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.exercises.enums import (
    Difficulty,
    ExerciseType,
    MediaType,
    MovementPattern,
)
from app.exercises.models import Exercise
from app.training_templates.models import (
    TrainingProgramTemplate,
    TrainingProgramTemplateSlot,
)
from app.training_templates.seed_data import TRAINING_PROGRAM_TEMPLATE_SEEDS
from app.training_templates.service import seed_training_program_templates

LEGACY_SOURCE_NAME = "Fitsho synthesis: Stronger By Science · Jeff Nippard · RP Strength"
LEGACY_SOURCE_URL = "https://www.strongerbyscience.com/exercise-order-video/"


EXPECTED_CANONICAL_SLUGS = {
    "t01-2-day-full-body-ab",
    "t02-3-day-upper-lower-full",
    "t03-3-day-upper-lower-upper",
    "t04-3-day-lower-upper-lower",
    "t05-4-day-upper-lower-2x",
    "t06-4-day-3-upper-1-lower",
    "t07-4-day-3-lower-1-upper",
    "t08-4-day-push-pull-quads-posterior",
    "t09-5-day-ppl-upper-lower",
    "t10-5-day-classic-body-part",
    "t11-5-day-ppl-upper-lower-priority",
    "t12-5-day-chest-specialization",
    "t13-5-day-back-specialization",
    "t14-5-day-leg-specialization",
    "t15-6-day-ppl-2x",
    "t16-6-day-advanced-body-part",
    "t17-6-day-balanced-specialization",
}


REAL_CATALOG_SLUGS = {
    "fedb-0750-smith-chair-squat",
    "fedb-1435-barbell-back-squat",
    "fedb-0042-barbell-front-squat",
    "fedb-2611-lever-horizontal-leg-press",
    "fedb-0585-lever-leg-extension",
    "fedb-0336-dumbbell-lunge",
    "fedb-0300-dumbbell-deadlift",
    "fedb-0599-lever-seated-leg-curl",
    "fedb-0586-lever-lying-leg-curl",
    "fedb-0668-rear-decline-bridge",
    "fedb-0605-lever-standing-calf-raise",
    "fedb-0577-lever-lying-chest-press",
    "fedb-1299-lever-incline-hammer-chest-press",
    "fedb-0025-barbell-bench-press",
    "fedb-0314-dumbbell-incline-bench-press",
    "fedb-1269-cable-standing-fly",
    "fedb-0581-lever-high-row",
    "owner-e0c26a271aac-barbell-bent-over-row",
    "owner-2a5de4dc7ba3-seated-cable-row",
    "fedb-0974-cable-close-grip-lat-pulldown",
    "fedb-0238-cable-straight-arm-pulldown",
    "fedb-0765-smith-seated-shoulder-press",
    "fedb-0289-seated-dumbbell-shoulder-press",
    "fedb-0553-military-press",
    "fedb-0584-lever-lateral-raise",
    "fedb-0178-cable-lateral-raise",
    "fedb-0602-lever-seated-reverse-fly",
    "fedb-0592-lever-preacher-curl",
    "fedb-0285-seated-alternating-dumbbell-curl",
    "fedb-0298-dumbbell-cross-body-hammer-curl",
    "fedb-0031-barbell-curl",
    "fedb-1723-cable-triceps-pushdown",
    "fedb-0200-cable-rope-triceps-pushdown",
    "fedb-0194-cable-rope-overhead-triceps-extension",
    "fedb-0095-barbell-shrug",
    "fedb-1452-lever-seated-crunch",
    "fedb-0464-front-plank",
    "fedb-0705-side-plank",
}


def _seed_real_catalog_exercises(db: Session, slugs: Iterable[str] = REAL_CATALOG_SLUGS) -> None:
    for slug in slugs:
        db.add(
            Exercise(
                slug=slug,
                name_en=slug.replace("-", " ").title(),
                name_fa="حرکت واقعی کتابخانه",
                difficulty=Difficulty.INTERMEDIATE,
                movement_pattern=MovementPattern.OTHER,
                exercise_type=ExerciseType.COMPOUND,
                instructions_en=["Set up safely.", "Use controlled form.", "Stop if pain appears."],
                instructions_fa=["ایمن آماده شو.", "فرم را کنترل کن.", "در صورت درد توقف کن."],
                safety_notes_en=["Use a controlled load."],
                safety_notes_fa=["از وزنه قابل‌کنترل استفاده کن."],
                media_path=f"/media/exercises/{slug}.gif",
                media_type=MediaType.GIF,
                source="free-exercise-db",
                source_id=f"test-{slug}",
                is_active=True,
                is_programmable=True,
            )
        )
    db.flush()


def _legacy_template(slug: str) -> TrainingProgramTemplate:
    return TrainingProgramTemplate(
        slug=slug,
        name_en="Legacy Fitsho Template",
        name_fa="قالب قدیمی فیتشو",
        description_en="Legacy catalog row.",
        description_fa="ردیف قدیمی کاتالوگ.",
        days_per_week=2,
        training_level="beginner",
        fitness_goal="build_muscle",
        focus_tags=["full_body"],
        intensity_methods=["standard"],
        programming_rationale=[],
        source_name=LEGACY_SOURCE_NAME,
        source_url=LEGACY_SOURCE_URL,
        is_active=True,
    )


def test_catalog_defines_exactly_seventeen_canonical_structures() -> None:
    canonical_slugs = {
        getattr(seed, "canonical_slug", None) for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS
    }

    assert canonical_slugs == EXPECTED_CANONICAL_SLUGS


def test_catalog_seed_requires_real_library_rows_and_creates_no_placeholders(db: Session) -> None:
    _seed_real_catalog_exercises(db)

    result = seed_training_program_templates(db)

    assert result.placeholder_slots == 0
    slots = list(db.scalars(select(TrainingProgramTemplateSlot)))
    assert slots
    assert all(slot.exercise_id is not None for slot in slots)


def test_catalog_seed_removes_all_legacy_source_rows_but_preserves_custom_rows(db: Session) -> None:
    _seed_real_catalog_exercises(db)
    legacy = [_legacy_template(f"legacy-fitsho-{index}") for index in range(3)]
    custom = TrainingProgramTemplate(
        slug="admin-custom-template",
        name_en="Admin Custom Template",
        name_fa="قالب سفارشی ادمین",
        description_en="Custom template.",
        description_fa="قالب سفارشی.",
        days_per_week=2,
        training_level="beginner",
        fitness_goal="build_muscle",
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

    assert db.scalar(
        select(func.count())
        .select_from(TrainingProgramTemplate)
        .where(
            TrainingProgramTemplate.source_name == LEGACY_SOURCE_NAME,
            TrainingProgramTemplate.source_url == LEGACY_SOURCE_URL,
        )
    ) == 0
    assert db.scalar(
        select(TrainingProgramTemplate).where(TrainingProgramTemplate.slug == custom.slug)
    ) is not None


def test_catalog_seed_is_idempotent_and_replaces_owned_days_and_slots(db: Session) -> None:
    _seed_real_catalog_exercises(db)

    first = seed_training_program_templates(db)
    second = seed_training_program_templates(db)

    assert second == first
    assert db.scalar(select(func.count()).select_from(TrainingProgramTemplate)) == first.templates
    assert db.scalar(select(func.count()).select_from(TrainingProgramTemplateSlot)) > 0


def test_catalog_slots_are_linked_to_active_programmable_non_placeholder_exercises(
    db: Session,
) -> None:
    _seed_real_catalog_exercises(db)
    seed_training_program_templates(db)

    slots = list(db.scalars(select(TrainingProgramTemplateSlot)))
    assert all(slot.exercise is not None for slot in slots)
    assert all(slot.exercise.is_active and slot.exercise.is_programmable for slot in slots)
    assert all(slot.exercise.source != "fitsho_training_template" for slot in slots)
    assert all(
        slot.placeholder_name_en is None and slot.placeholder_name_fa is None for slot in slots
    )


def test_catalog_days_guidance_and_prescriptions_match_document_contract() -> None:
    assert len({seed.canonical_slug for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS}) == 17
    assert all(
        5 <= len(day.slots) <= 9
        for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS
        for day in seed.days
    )
    assert all(
        len(seed.programming_rationale) == 5
        and all(
            reason.title_en
            and reason.title_fa
            and reason.detail_en
            and reason.detail_fa
            for reason in seed.programming_rationale
        )
        for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS
    )
    assert all(
        1 <= slot.sets <= 4
        and slot.rep_min <= slot.rep_max
        and slot.target_rir in {1, 2, 3}
        and 45 <= slot.rest_seconds <= 150
        for seed in TRAINING_PROGRAM_TEMPLATE_SEEDS
        for day in seed.days
        for slot in day.slots
    )


def test_missing_real_library_row_fails_instead_of_creating_a_placeholder(db: Session) -> None:
    with pytest.raises(ValueError, match="Missing active programmable Exercise Library movement"):
        seed_training_program_templates(db)
