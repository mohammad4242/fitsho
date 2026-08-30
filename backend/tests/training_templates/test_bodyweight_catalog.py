from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exercises.service import seed_exercises
from app.profile.enums import ExperienceLevel
from app.training_templates.bodyweight_reference import load_bodyweight_template
from app.training_templates.engine_reference import load_template_references
from app.training_templates.models import TrainingProgramTemplate
from app.training_templates.service import (
    list_training_program_templates,
    seed_training_program_templates,
)
from app.workouts.bodyweight_templates import (
    bodyweight_template_fingerprint,
    get_bodyweight_template,
)
from tests.training_templates.catalog_fixture import seed_real_catalog_exercises


def _seed_catalog(db: Session) -> None:
    seed_exercises(db)
    seed_real_catalog_exercises(db)
    seed_training_program_templates(db)


def test_bodyweight_templates_are_admin_catalog_rows_but_not_engine_references(
    db: Session,
) -> None:
    _seed_catalog(db)

    templates = list_training_program_templates(db)
    fixed = [template for template in templates if template.category == "bodyweight_fixed"]

    assert len(fixed) == 6
    assert {template.slug for template in fixed} == {
        "bw-first-month-2d-v1",
        "bw-first-month-3d-v1",
        "bw-first-month-4d-v1",
        "bw-beginner-2d-v1",
        "bw-beginner-3d-v1",
        "bw-beginner-4d-v1",
    }
    assert all(template.engine_eligible is False for template in fixed)
    assert not {reference.slug for reference in load_template_references(db)}.intersection(
        template.slug for template in fixed
    )


def test_bodyweight_catalog_preserves_duration_slots(db: Session) -> None:
    _seed_catalog(db)

    template = db.scalar(
        select(TrainingProgramTemplate).where(
            TrainingProgramTemplate.slug == "bw-first-month-2d-v1"
        )
    )
    assert template is not None
    front_plank = next(
        slot
        for day in template.days
        for slot in day.slots
        if slot.exercise_slug_hint == "fedb-0464-front-plank"
    )
    assert front_plank.prescription_mode.value == "duration"
    assert front_plank.rep_min is None
    assert front_plank.rep_max is None
    assert front_plank.target_rir is None
    assert (front_plank.duration_min_seconds, front_plank.duration_max_seconds) == (20, 30)


def test_bodyweight_route_reads_admin_catalog_edits(db: Session) -> None:
    _seed_catalog(db)
    template = db.scalar(
        select(TrainingProgramTemplate).where(
            TrainingProgramTemplate.slug == "bw-first-month-2d-v1"
        )
    )
    assert template is not None
    original = next(slot for day in template.days for slot in day.slots)
    original.exercise_slug_hint = "fedb-drv-push-ups-push-up"
    db.flush()

    loaded = load_bodyweight_template(db, ExperienceLevel.FIRST_MONTH, 2)

    assert loaded is not None
    assert loaded.days[0].exercises[0].exercise_slug == "fedb-drv-push-ups-push-up"


def test_bodyweight_catalog_preserves_upper_lower_day_labels(db: Session) -> None:
    _seed_catalog(db)

    template = db.scalar(
        select(TrainingProgramTemplate).where(
            TrainingProgramTemplate.slug == "bw-beginner-4d-v1"
        )
    )
    assert template is not None
    assert [day.title_en for day in template.days] == [
        "Upper A",
        "Lower A",
        "Upper B",
        "Lower B",
    ]


def test_catalog_templates_match_the_approved_fixed_library(db: Session) -> None:
    _seed_catalog(db)

    for level in (ExperienceLevel.FIRST_MONTH, ExperienceLevel.BEGINNER):
        for days in (2, 3, 4):
            catalog_template = load_bodyweight_template(db, level, days)
            library_template = get_bodyweight_template(level, days)
            assert catalog_template is not None
            assert library_template is not None
            assert bodyweight_template_fingerprint(
                catalog_template
            ) == bodyweight_template_fingerprint(library_template)
