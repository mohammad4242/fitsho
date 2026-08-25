import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.training_templates.engine_reference import load_template_references
from app.training_templates.models import TrainingProgramTemplate
from app.training_templates.service import seed_training_program_templates
from app.workouts.program_engine.enums import SplitType
from tests.training_templates.catalog_fixture import seed_real_catalog_exercises


def test_engine_references_preserve_linked_slot_and_adaptation_metadata(db: Session) -> None:
    seed_real_catalog_exercises(db)
    seed_training_program_templates(db)

    reference = next(
        item for item in load_template_references(db) if item.slug == "t14-5-day-leg-specialization"
    )

    assert reference.days_per_week == 5
    assert all(slot.exercise_id is not None for day in reference.days for slot in day.slots)
    assert all(
        slot.adaptation_priority in {"core", "accessory"}
        for day in reference.days
        for slot in day.slots
    )


def test_engine_reference_rejects_noncanonical_persisted_focus_tags(db: Session) -> None:
    seed_real_catalog_exercises(db)
    seed_training_program_templates(db)
    template = db.scalar(
        select(TrainingProgramTemplate).where(
            TrainingProgramTemplate.slug == "t10-5-day-classic-body-part"
        )
    )
    assert template is not None
    template.focus_tags = ["classic"]
    db.flush()

    with pytest.raises(ValueError, match="Unknown template focus tag"):
        load_template_references(db)


@pytest.mark.parametrize(
    ("slug", "expected"),
    (
        ("t01-2-day-full-body-ab", SplitType.FULL_BODY),
        ("t05-4-day-upper-lower-2x", SplitType.UPPER_LOWER),
        (
            "t09-5-day-ppl-upper-lower",
            SplitType.PUSH_PULL_LEGS_UPPER_LOWER,
        ),
        ("t10-5-day-classic-body-part", SplitType.BODY_PART_ROTATION),
    ),
)
def test_engine_reference_preserves_canonical_split_identity(
    db: Session,
    slug: str,
    expected: SplitType,
) -> None:
    seed_real_catalog_exercises(db)
    seed_training_program_templates(db)

    reference = next(item for item in load_template_references(db) if item.slug == slug)

    assert reference.split_type is expected
