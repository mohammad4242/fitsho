from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.schemas import AdminTrainingTemplateSlotWrite
from app.exercises.enums import (
    MediaType,
    MovementPattern,
    MuscleFocus,
    MuscleGroup,
    PrescriptionMode,
)
from app.exercises.models import Exercise
from app.exercises.service import seed_exercises
from app.profile.enums import ExperienceLevel, FitnessGoal
from app.profile.training_compatibility import (
    ResistanceTrainingDayStatus,
    resistance_training_day_status,
)
from app.training_templates.models import (
    TrainingProgramTemplate,
    TrainingProgramTemplateSlot,
    TrainingTemplateSlotPriority,
)
from app.training_templates.seed_data import (
    SOURCE_NAME,
    SOURCE_URL,
    TRAINING_PROGRAM_TEMPLATE_SEEDS,
    TemplateDaySeed,
    TemplateSlotSeed,
)
from app.training_templates.service import seed_training_program_templates

EXPECTED_RETIRED_REDUNDANT_TEMPLATE_SLUGS = frozenset(
    {
        "two-day-full-body-fat-loss-beginner",
        "two-day-full-body-general-fitness-beginner",
        "three-day-full-body-fat-loss-beginner",
        "three-day-full-body-general-fitness-beginner",
        "five-day-ppl-fat-loss-intermediate",
        "six-day-ppl-fat-loss-advanced",
    }
)
EXPECTED_RETIRED_UNSUPPORTED_TEMPLATE_SLUGS = frozenset(
    {
        "two-day-full-body-superset",
        "five-day-beginner-body-part-foundation",
    }
)
EXPECTED_STRUCTURAL_RECLASSIFIED_TEMPLATE_SLUGS = frozenset(
    {
        "two-day-full-body-strength-beginner",
        "three-day-full-body-strength-beginner",
        "three-day-full-body-strength-intermediate",
        "four-day-upper-lower-strength-intermediate",
        "four-day-upper-lower-strength-advanced",
        "five-day-strength-intermediate",
        "five-day-strength-advanced",
        "six-day-push-pull-legs-strength",
        "three-day-full-body-fat-loss-intermediate",
        "four-day-upper-lower-fat-loss-intermediate",
        "four-day-upper-lower-fat-loss-advanced",
        "five-day-ppl-fat-loss-advanced",
        "three-day-full-body-general-fitness-intermediate",
        "four-day-upper-lower-general-fitness-intermediate",
    }
)


def test_seed_adds_current_template_library_for_every_supported_training_frequency(
    db: Session,
) -> None:
    seed_exercises(db)

    result = seed_training_program_templates(db)

    assert result.templates == 49
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
        patterns = {slot.movement_pattern for day in template.days for slot in day.slots}
        assert MovementPattern.HORIZONTAL_PUSH in patterns, template.slug
        assert patterns & {MovementPattern.HORIZONTAL_PULL, MovementPattern.VERTICAL_PULL}, (
            template.slug
        )
        assert patterns & {
            MovementPattern.SQUAT,
            MovementPattern.LUNGE,
            MovementPattern.KNEE_EXTENSION,
        }, template.slug
        assert patterns & {MovementPattern.HIP_HINGE, MovementPattern.HIP_EXTENSION}, template.slug


def test_audited_library_contains_structural_variants_not_goal_duplicates() -> None:
    assert len(TRAINING_PROGRAM_TEMPLATE_SEEDS) == 49
    seed_slugs = {template.slug for template in TRAINING_PROGRAM_TEMPLATE_SEEDS}

    assert not seed_slugs.intersection(EXPECTED_RETIRED_REDUNDANT_TEMPLATE_SLUGS)
    assert not seed_slugs.intersection(EXPECTED_RETIRED_UNSUPPORTED_TEMPLATE_SLUGS)
    assert EXPECTED_STRUCTURAL_RECLASSIFIED_TEMPLATE_SLUGS.issubset(seed_slugs)
    assert all(
        template.fitness_goal is FitnessGoal.BUILD_MUSCLE
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
    )
    assert all(
        not {"strength", "fat_loss", "general_fitness"}.intersection(template.focus_tags)
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
    )


def test_audited_library_keeps_unique_goal_era_structures() -> None:
    seed_slugs = {template.slug for template in TRAINING_PROGRAM_TEMPLATE_SEEDS}

    assert {
        "three-day-full-body-strength-intermediate",
        "four-day-upper-lower-strength-advanced",
        "four-day-upper-lower-fat-loss-intermediate",
        "five-day-ppl-fat-loss-advanced",
        "three-day-full-body-general-fitness-intermediate",
        "four-day-upper-lower-general-fitness-intermediate",
    }.issubset(seed_slugs)


def test_active_seeded_library_excludes_unsupported_days_and_levels(db: Session) -> None:
    seed_exercises(db)
    seed_training_program_templates(db)

    active_templates = list(
        db.scalars(
            select(TrainingProgramTemplate).where(TrainingProgramTemplate.is_active.is_(True))
        )
    )

    assert all(
        resistance_training_day_status(template.training_level, template.days_per_week)
        is not ResistanceTrainingDayStatus.UNSUPPORTED
        for template in active_templates
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
            ordering = [_slot_ordering_key(slot) for slot in day.slots]
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
    assert result.templates == 49
    for days_per_week in (4, 5):
        bucket = [template for template in templates if template.days_per_week == days_per_week]
        assert len(bucket) == {4: 16, 5: 11}[days_per_week]
        assert {template.training_level for template in bucket} == {
            ExperienceLevel.FIRST_MONTH,
            ExperienceLevel.BEGINNER,
            ExperienceLevel.INTERMEDIATE,
            ExperienceLevel.ADVANCED,
        } - (
            {ExperienceLevel.FIRST_MONTH, ExperienceLevel.BEGINNER} if days_per_week == 5 else set()
        )
        tags = {tag for template in bucket for tag in template.focus_tags}
        assert {"chest_priority", "back_priority"}.issubset(tags)


def test_first_month_has_only_conservative_two_three_and_four_day_structures() -> None:
    templates = tuple(
        template
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
        if template.training_level is ExperienceLevel.FIRST_MONTH
    )

    assert {template.days_per_week for template in templates} == {2, 3, 4}
    assert len(templates) == 3
    assert all(
        template.intensity_methods == ("standard",)
        or tuple(method.value for method in template.intensity_methods) == ("standard",)
        for template in templates
    )
    assert all(5 <= len(day.slots) <= 6 for template in templates for day in template.days)
    assert all("specialization" not in template.focus_tags for template in templates)


def test_template_slot_default_is_accessory_and_seed_priorities_are_intentional() -> None:
    default_slot = TemplateSlotSeed(
        exercise_slug_hint="test-slot",
        catalog_slug_hints=("test-slot",),
        target_muscles=(MuscleGroup.BICEPS,),
        movement_pattern=MovementPattern.ELBOW_FLEXION,
    )

    assert default_slot.adaptation_priority.value == "accessory"
    assert all(
        any(slot.adaptation_priority.value == "core" for slot in day.slots)
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
        for day in template.days
    )


def test_new_persisted_and_admin_slots_default_to_accessory() -> None:
    column = TrainingProgramTemplateSlot.__table__.c.adaptation_priority
    payload = AdminTrainingTemplateSlotWrite(
        exercise_id="11111111-1111-1111-1111-111111111111",
        target_muscles=[MuscleGroup.BICEPS],
        movement_pattern=MovementPattern.ELBOW_FLEXION,
        sets=3,
        rep_min=8,
        rep_max=12,
        target_rir=2,
        rest_seconds=60,
    )

    assert column.default is not None
    assert column.default.arg is TrainingTemplateSlotPriority.ACCESSORY
    assert column.server_default is not None
    assert str(column.server_default.arg) == "accessory"
    assert payload.adaptation_priority is TrainingTemplateSlotPriority.ACCESSORY


def test_mixed_sessions_do_not_make_every_direct_muscle_slot_core() -> None:
    template = next(
        item
        for item in TRAINING_PROGRAM_TEMPLATE_SEEDS
        if item.slug == "two-day-first-month-full-body"
    )
    second_day = template.days[1]
    priorities = {slot.exercise_slug_hint: slot.adaptation_priority for slot in second_day.slots}

    assert priorities["romanian-deadlift"] is TrainingTemplateSlotPriority.CORE
    assert priorities["incline-dumbbell-bench-press"] is TrainingTemplateSlotPriority.CORE
    assert priorities["lat-pulldown"] is TrainingTemplateSlotPriority.ACCESSORY
    assert priorities["dead-bug"] is TrainingTemplateSlotPriority.ACCESSORY
    assert all(
        slot.adaptation_priority.value != "core"
        for template in TRAINING_PROGRAM_TEMPLATE_SEEDS
        if "specialization" not in template.focus_tags
        for day in template.days
        for slot in day.slots
        if slot.exercise_slug_hint
        in {
            "dumbbell-curl",
            "hammer-curl",
            "standing-calf-raise",
            "dumbbell-lateral-raise",
        }
        and not set(slot.target_muscles).intersection(day.direct_target_muscles)
    )


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


def test_side_plank_placeholder_uses_duration_metadata(db: Session) -> None:
    seed_exercises(db)
    seed_training_program_templates(db)

    side_plank = db.scalar(select(Exercise).where(Exercise.slug == "side-plank"))

    assert side_plank is not None
    assert side_plank.source == "fitsho_training_template"
    assert side_plank.source_id == "side-plank"
    assert side_plank.prescription_mode is PrescriptionMode.DURATION
    assert (side_plank.duration_min_seconds, side_plank.duration_max_seconds) == (20, 40)


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

    assert result.templates == 49
    assert (
        db.scalar(
            select(TrainingProgramTemplate).where(
                TrainingProgramTemplate.slug == "two-day-full-body-foundation"
            )
        )
        is not None
    )


def test_reseed_replaces_legacy_managed_focus_tags_with_canonical_tags(db: Session) -> None:
    seed_exercises(db)
    seed_training_program_templates(db)
    template = db.scalar(
        select(TrainingProgramTemplate).where(
            TrainingProgramTemplate.slug == "four-day-classic-body-part"
        )
    )
    assert template is not None
    template.focus_tags = ["classic", "body_part_rotation", "classic"]
    db.commit()

    seed_training_program_templates(db)

    refreshed = db.get(TrainingProgramTemplate, template.id)
    assert refreshed is not None
    assert refreshed.focus_tags == ["body_part_rotation", "balanced"]


def test_reseed_deactivates_obsolete_fitsho_templates_but_keeps_custom_templates(
    db: Session,
) -> None:
    seed_exercises(db)

    obsolete = TrainingProgramTemplate(
        slug="two-day-full-body-general-fitness-beginner",
        name_en="Obsolete Fitsho Template",
        name_fa="قالب قدیمی فیتشو",
        description_en="Obsolete seeded template.",
        description_fa="قالب بذر قدیمی.",
        days_per_week=2,
        training_level=ExperienceLevel.BEGINNER,
        fitness_goal=FitnessGoal.BUILD_MUSCLE,
        focus_tags=["full_body"],
        intensity_methods=["standard"],
        programming_rationale=[],
        source_name=SOURCE_NAME,
        source_url=SOURCE_URL,
        is_active=True,
    )
    custom = TrainingProgramTemplate(
        slug="admin-custom-template",
        name_en="Admin Custom Template",
        name_fa="قالب سفارشی ادمین",
        description_en="Custom template.",
        description_fa="قالب سفارشی.",
        days_per_week=2,
        training_level=ExperienceLevel.BEGINNER,
        fitness_goal=FitnessGoal.BUILD_MUSCLE,
        focus_tags=["full_body"],
        intensity_methods=["standard"],
        programming_rationale=[],
        source_name="Fitsho admin library",
        source_url="https://fitsho.local/admin-library",
        is_active=True,
    )
    db.add_all((obsolete, custom))
    db.commit()

    seed_training_program_templates(db)

    assert db.get(TrainingProgramTemplate, obsolete.id).is_active is False
    assert db.get(TrainingProgramTemplate, custom.id).is_active is True


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
