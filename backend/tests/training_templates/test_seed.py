from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exercises.models import Exercise
from app.exercises.service import seed_exercises
from app.profile.enums import ExperienceLevel
from app.training_templates.models import TrainingProgramTemplate, TrainingProgramTemplateSlot
from app.training_templates.service import seed_training_program_templates


def test_seed_adds_five_templates_for_every_supported_training_frequency(db: Session) -> None:
    seed_exercises(db)

    result = seed_training_program_templates(db)

    assert result.templates == 35
    templates = list(db.scalars(select(TrainingProgramTemplate)))
    assert {template.days_per_week for template in templates} == {2, 3, 4, 5, 6}
    for days_per_week in range(2, 7):
        assert sum(template.days_per_week == days_per_week for template in templates) >= 5


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


def test_seed_keeps_unavailable_exercise_as_explicit_placeholder(db: Session) -> None:
    seed_exercises(db)

    seed_training_program_templates(db)

    placeholder = db.scalar(
        select(TrainingProgramTemplateSlot).where(
            TrainingProgramTemplateSlot.exercise_slug_hint == "cable-pullover"
        )
    )
    assert placeholder is not None
    assert placeholder.exercise_id is None
    assert placeholder.placeholder_name_en == "Cable Pullover"


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
