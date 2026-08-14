from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exercises.enums import MediaType, MovementPattern, MuscleFocus, MuscleGroup
from app.exercises.models import Exercise
from app.exercises.service import seed_exercises
from app.profile.enums import ExperienceLevel
from app.training_templates.models import TrainingProgramTemplate, TrainingProgramTemplateSlot
from app.training_templates.seed_data import (
    TRAINING_PROGRAM_TEMPLATE_SEEDS,
    TemplateDaySeed,
    TemplateSlotSeed,
)
from app.training_templates.service import seed_training_program_templates


def test_seed_adds_five_templates_for_every_supported_training_frequency(db: Session) -> None:
    seed_exercises(db)

    result = seed_training_program_templates(db)

    assert result.templates == 35
    templates = list(db.scalars(select(TrainingProgramTemplate)))
    assert {template.days_per_week for template in templates} == {2, 3, 4, 5, 6}
    for days_per_week in range(2, 7):
        assert sum(template.days_per_week == days_per_week for template in templates) >= 5


def test_active_library_offers_two_through_six_days_and_only_full_body_two_day_templates(
    db: Session,
) -> None:
    seed_exercises(db)
    seed_training_program_templates(db)

    active_templates = list(
        db.scalars(
            select(TrainingProgramTemplate).where(TrainingProgramTemplate.is_active.is_(True))
        )
    )

    assert {template.days_per_week for template in active_templates} == {2, 3, 4, 5, 6}
    assert all(
        "full_body" in template.focus_tags
        for template in active_templates
        if template.days_per_week == 2
    )

    two_day_seeds = [
        template for template in TRAINING_PROGRAM_TEMPLATE_SEEDS if template.days_per_week == 2
    ]
    for template in two_day_seeds:
        for day in template.days:
            patterns = {slot.movement_pattern for slot in day.slots}
            assert MovementPattern.HORIZONTAL_PUSH in patterns, template.slug
            assert patterns & {MovementPattern.HORIZONTAL_PULL, MovementPattern.VERTICAL_PULL}, (
                template.slug
            )
            assert patterns & {
                MovementPattern.SQUAT,
                MovementPattern.LUNGE,
                MovementPattern.KNEE_EXTENSION,
            }, template.slug
            assert patterns & {MovementPattern.HIP_HINGE, MovementPattern.HIP_EXTENSION}, (
                template.slug
            )


def test_every_template_session_contains_between_five_and_nine_exercises() -> None:
    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        for day in template.days:
            assert 5 <= len(day.slots) <= 9, f"{template.slug}: {day.title_en}"


def test_every_template_includes_five_bilingual_programming_reasons() -> None:
    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        assert len(template.programming_rationale) == 5, template.slug
        assert all(reason.title_en and reason.title_fa for reason in template.programming_rationale)
        assert all(
            reason.detail_en and reason.detail_fa for reason in template.programming_rationale
        )


def test_template_sessions_place_main_work_before_isolation_and_intensity_methods_last() -> None:
    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        for day in template.days:
            ordering = [
                _slot_ordering_key(slot)
                for slot in day.slots
            ]
            assert ordering == sorted(ordering), f"{template.slug}: {day.title_en}"


def test_chest_priority_session_places_compound_presses_before_fly() -> None:
    template = next(
        item for item in TRAINING_PROGRAM_TEMPLATE_SEEDS if item.slug == "three-day-chest-priority"
    )
    day = next(item for item in template.days if item.title_en == "Chest + Shoulders")
    slugs = [slot.exercise_slug_hint for slot in day.slots]

    assert slugs.index("dumbbell-bench-press") < slugs.index("cable-fly")
    assert slugs.index("smith-machine-shoulder-press") < slugs.index("cable-fly")


def _slot_ordering_key(slot: TemplateSlotSeed) -> tuple[int, int]:
    movement_pattern = slot.movement_pattern
    intensity_method = slot.intensity_method
    main_patterns = {
        MovementPattern.SQUAT,
        MovementPattern.HIP_HINGE,
        MovementPattern.LUNGE,
        MovementPattern.HORIZONTAL_PUSH,
        MovementPattern.HORIZONTAL_PULL,
        MovementPattern.VERTICAL_PUSH,
        MovementPattern.VERTICAL_PULL,
        MovementPattern.HIP_EXTENSION,
    }
    isolation_slugs = {
        "cable-fly",
        "pec-deck-fly",
        "cable-pullover",
        "rear-delt-fly",
        "face-pull",
    }
    return (
        0 if intensity_method.value == "standard" else 1,
        0
        if movement_pattern in main_patterns and slot.exercise_slug_hint not in isolation_slugs
        else 1,
    )


def test_seed_expands_four_and_five_day_reference_library_across_levels(db: Session) -> None:
    seed_exercises(db)

    result = seed_training_program_templates(db)

    templates = list(db.scalars(select(TrainingProgramTemplate)))
    assert result.templates == 35
    for days_per_week in (4, 5):
        bucket = [template for template in templates if template.days_per_week == days_per_week]
        assert len(bucket) == 10
        assert {template.training_level for template in bucket} == {
            ExperienceLevel.BEGINNER,
            ExperienceLevel.INTERMEDIATE,
            ExperienceLevel.ADVANCED,
        }
        tags = {tag for template in bucket for tag in template.focus_tags}
        assert {"chest_priority", "back_priority"}.issubset(tags)


def test_specialized_body_part_templates_meet_direct_movement_floors() -> None:
    for template in TRAINING_PROGRAM_TEMPLATE_SEEDS:
        if template.days_per_week < 4 or "body_part_rotation" not in template.focus_tags:
            continue

        exposures: Counter[MuscleGroup] = Counter()
        for day in template.days:
            _assert_session_movement_floors(day)
            for muscle in MuscleGroup:
                if _direct_slot_count(day, (muscle,)):
                    exposures[muscle] += 1

        assert all(count <= 2 for count in exposures.values()), template.slug


def _assert_session_movement_floors(day: TemplateDaySeed) -> None:
    large_targets = {
        "Chest": (MuscleGroup.CHEST,),
        "Back": (MuscleGroup.BACK,),
        "Shoulder": (MuscleGroup.SHOULDERS,),
        "Delts": (MuscleGroup.SHOULDERS,),
        "Quadriceps": (MuscleGroup.QUADRICEPS,),
        "Hamstrings": (MuscleGroup.HAMSTRINGS,),
        "Glutes": (MuscleGroup.GLUTES,),
        "Legs": (MuscleGroup.QUADRICEPS, MuscleGroup.HAMSTRINGS, MuscleGroup.GLUTES),
    }
    small_targets = {
        "Arms": (MuscleGroup.BICEPS, MuscleGroup.TRICEPS),
        "Biceps": (MuscleGroup.BICEPS,),
        "Triceps": (MuscleGroup.TRICEPS,),
        "Traps": (MuscleGroup.TRAPS,),
        "Calves": (MuscleGroup.CALVES,),
        "Core": (MuscleGroup.ABS,),
    }
    for label, muscles in large_targets.items():
        if label in day.title_en:
            assert _direct_slot_count(day, muscles) >= 3, day.title_en
    for label, muscles in small_targets.items():
        if label in day.title_en:
            if label == "Arms":
                for muscle in muscles:
                    assert _direct_slot_count(day, (muscle,)) >= 2, day.title_en
            else:
                assert _direct_slot_count(day, muscles) >= 2, day.title_en


def _direct_slot_count(day: TemplateDaySeed, muscles: tuple[MuscleGroup, ...]) -> int:
    return sum(bool(set(slot.target_muscles).intersection(muscles)) for slot in day.slots)


def test_seed_creates_missing_template_exercise_as_safe_catalog_placeholder(db: Session) -> None:
    seed_exercises(db)

    seed_training_program_templates(db)

    slot = db.scalar(
        select(TrainingProgramTemplateSlot).where(
            TrainingProgramTemplateSlot.exercise_slug_hint == "cable-pullover"
        )
    )
    assert slot is not None
    assert slot.exercise is not None
    assert slot.exercise.slug == "cable-pullover"
    assert slot.exercise.primary_muscle is MuscleGroup.BACK
    assert slot.exercise.muscle_focus is MuscleFocus.LATS
    assert slot.exercise.needs_review is True
    assert slot.exercise.is_programmable is False
    assert slot.exercise.media_type is MediaType.PLACEHOLDER


def test_template_placeholder_seed_preserves_admin_media_and_review_updates(db: Session) -> None:
    seed_exercises(db)
    seed_training_program_templates(db)
    placeholder = db.scalar(select(Exercise).where(Exercise.slug == "cable-pullover"))
    assert placeholder is not None
    placeholder.media_path = "/media/exercises/cable-pullover.gif"
    placeholder.media_type = MediaType.GIF
    placeholder.needs_review = False
    placeholder.is_programmable = True
    db.commit()

    seed_training_program_templates(db)

    stored = db.scalar(select(Exercise).where(Exercise.slug == "cable-pullover"))
    assert stored is not None
    assert stored.media_path == "/media/exercises/cable-pullover.gif"
    assert stored.media_type is MediaType.GIF
    assert stored.needs_review is False
    assert stored.is_programmable is True


def test_seed_resolves_a_curated_imported_catalog_alias(db: Session) -> None:
    seed_exercises(db)
    exercise = db.scalar(select(Exercise).where(Exercise.slug == "dumbbell-bench-press"))
    assert exercise is not None
    exercise.slug = "fedb-0025-barbell-bench-press"
    db.commit()

    seed_training_program_templates(db)

    slot = db.scalar(
        select(TrainingProgramTemplateSlot).where(
            TrainingProgramTemplateSlot.exercise_slug_hint == "dumbbell-bench-press"
        )
    )
    assert slot is not None
    assert slot.exercise_id == exercise.id


def test_seed_can_be_rerun_without_duplicate_template_days(db: Session) -> None:
    seed_exercises(db)
    seed_training_program_templates(db)

    result = seed_training_program_templates(db)

    assert result.templates == 35
    assert (
        db.scalar(
            select(TrainingProgramTemplate).where(
                TrainingProgramTemplate.slug == "two-day-full-body-foundation"
            )
        )
        is not None
    )


def test_seed_persists_template_programming_reasons(db: Session) -> None:
    seed_exercises(db)
    seed_training_program_templates(db)

    template = db.scalar(
        select(TrainingProgramTemplate).where(
            TrainingProgramTemplate.slug == "four-day-classic-body-part"
        )
    )

    assert template is not None
    assert len(template.programming_rationale) == 5
    assert template.programming_rationale[0]["title_fa"] == "ترتیب حرکات"
