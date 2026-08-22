import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exercises.service import seed_exercises
from app.training_templates.engine_reference import load_template_references
from app.training_templates.models import TrainingProgramTemplate
from app.training_templates.service import seed_training_program_templates


def test_engine_references_preserve_linked_slot_and_adaptation_metadata(db: Session) -> None:
    seed_exercises(db)
    seed_training_program_templates(db)

    reference = next(
        item
        for item in load_template_references(db)
        if item.slug == "five-day-advanced-leg-specialization"
    )
    paired_slots = [
        slot for day in reference.days for slot in day.slots if slot.superset_group == "leg-calf"
    ]

    assert reference.days_per_week == 5
    assert len(paired_slots) == 2
    assert all(slot.adaptation_priority == "accessory" for slot in paired_slots)
    assert all(slot.exercise_id is None or slot.exercise_id for slot in paired_slots)


def test_engine_reference_rejects_noncanonical_persisted_focus_tags(db: Session) -> None:
    seed_exercises(db)
    seed_training_program_templates(db)
    template = db.scalar(
        select(TrainingProgramTemplate).where(
            TrainingProgramTemplate.slug == "four-day-classic-body-part"
        )
    )
    assert template is not None
    template.focus_tags = ["classic"]
    db.flush()

    with pytest.raises(ValueError, match="Unknown template focus tag"):
        load_template_references(db)
