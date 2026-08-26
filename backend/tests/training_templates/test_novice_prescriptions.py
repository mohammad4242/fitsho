from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exercises.enums import MovementPattern
from app.profile.enums import ExperienceLevel
from app.training_templates import service
from app.training_templates.models import (
    TrainingProgramTemplate,
    TrainingProgramTemplateDay,
    TrainingProgramTemplateSlot,
)
from app.training_templates.seed_data import (
    CANONICAL_TEMPLATE_DEFINITIONS,
    TRAINING_PROGRAM_TEMPLATE_SEEDS,
)


def test_first_month_and_beginner_seed_slots_use_role_specific_prescriptions() -> None:
    definitions = {
        definition.canonical_slug: definition for definition in CANONICAL_TEMPLATE_DEFINITIONS
    }
    expected = {
        "P": (3, 8, 12),
        "S": (3, 8, 12),
        "I": (3, 10, 15),
    }

    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        level = template.supported_levels[0]
        if level not in {ExperienceLevel.FIRST_MONTH, ExperienceLevel.BEGINNER}:
            continue
        definition = definitions[template.canonical_slug]
        for day, expected_slots in zip(template.days, definition.day_specs, strict=True):
            for slot, (_, role) in zip(day.slots, expected_slots, strict=True):
                assert (slot.sets, slot.rep_min, slot.rep_max) == expected[role]


def test_novice_upgrade_updates_owned_defaults_and_preserves_custom_prescriptions(
    db: Session,
) -> None:
    from tests.training_templates.catalog_fixture import seed_real_catalog_exercises

    seed_real_catalog_exercises(db)
    service.seed_training_program_templates(db)
    managed = db.scalar(
        select(TrainingProgramTemplate).where(
            TrainingProgramTemplate.slug == "p01-2-day-full-body-ab-first-month"
        )
    )
    assert managed is not None
    db.refresh(managed)
    db.refresh(managed.days[0])
    edited_slot = managed.days[0].slots[0]
    edited_slot.sets = 4
    edited_slot.rep_min = 6
    edited_slot.rep_max = 10
    untouched_slot = managed.days[0].slots[1]
    untouched_slot.sets = 2
    untouched_slot.rep_min = 10
    untouched_slot.rep_max = 15
    custom = TrainingProgramTemplate(
        slug=f"custom-novice-{uuid4().hex}",
        name_en="Custom novice template",
        name_fa="الگوی سفارشی مبتدی",
        description_en="Custom.",
        description_fa="سفارشی.",
        days_per_week=2,
        supported_levels=[ExperienceLevel.BEGINNER.value],
        focus_tags=["full_body"],
        intensity_methods=["standard"],
        programming_rationale=[],
        source_name="Fitsho admin library",
        source_url="https://fitsho.local/admin-library",
        is_active=True,
    )
    custom.days.append(
        TrainingProgramTemplateDay(
            day_number=1,
            title_en="Custom day",
            title_fa="روز سفارشی",
            structure_focus="full_body",
            direct_target_muscles=["chest"],
            slots=[
                TrainingProgramTemplateSlot(
                    slot_order=1,
                    exercise_slug_hint="custom-exercise",
                    target_muscles=["chest"],
                    movement_pattern=MovementPattern.HORIZONTAL_PUSH,
                    sets=2,
                    rep_min=10,
                    rep_max=15,
                    target_rir=3,
                    rest_seconds=90,
                )
            ],
        )
    )
    db.add(custom)
    db.flush()

    upgrade = getattr(service, "upgrade_novice_template_prescriptions", None)
    assert callable(upgrade)
    assert upgrade(db) == 1

    db.expire_all()
    refreshed_managed = db.scalar(
        select(TrainingProgramTemplate).where(
            TrainingProgramTemplate.slug == "p01-2-day-full-body-ab-first-month"
        )
    )
    assert refreshed_managed is not None
    db.refresh(refreshed_managed)
    edited_signature = (
        refreshed_managed.days[0].slots[0].sets,
        refreshed_managed.days[0].slots[0].rep_min,
        refreshed_managed.days[0].slots[0].rep_max,
    )
    untouched_signature = (
        refreshed_managed.days[0].slots[1].sets,
        refreshed_managed.days[0].slots[1].rep_min,
        refreshed_managed.days[0].slots[1].rep_max,
    )
    assert edited_signature == (4, 6, 10)
    assert untouched_signature == (3, 8, 12)

    refreshed_custom = db.scalar(
        select(TrainingProgramTemplate).where(TrainingProgramTemplate.id == custom.id)
    )
    assert refreshed_custom is not None
    db.refresh(refreshed_custom)
    custom_signature = (
        refreshed_custom.days[0].slots[0].sets,
        refreshed_custom.days[0].slots[0].rep_min,
        refreshed_custom.days[0].slots[0].rep_max,
    )
    assert custom_signature == (2, 10, 15)
